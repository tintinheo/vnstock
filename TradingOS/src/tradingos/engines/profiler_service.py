"""Profiler Service — orchestrates full FR-2 ticker profile pipeline."""
from __future__ import annotations

import traceback
from datetime import datetime

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_foreign_flow, fetch_put_through_deals, fetch_quote, fetch_realtime
from ..data.fetcher import fetch_usdvnd, fetch_vn10y_bond_yield, fetch_sbv_omo_net
from ..data.fetcher import fetch_earnings_calendar, fetch_financial_statements, fetch_intraday_5m
from ..data.fiinquant_provider import fiin as _fiin_provider
from ..data.dnse_provider import dnse as _dnse_provider
from ..core.intraday_cvd import compute_intraday_cvd
from ..core.orderbook import compute_order_book_imbalance
from ..data.cache import cache
from ..data.schemas import TickerProfile, ProfilerRequest, TradingSignal
from ..core import (
    compute_indicators,
    run_amf, detect_amd_phase, volume_quality_score,
    compute_smart_money_score, detect_stealth_accumulation,
    detect_whale_distribution, mode_w_entry_params,
    detect_patterns,
    detect_hmm_state, compute_omega,
    compute_mfpm,
    compute_position_size,
    compute_atr_position_size,
    generate_signal_text,
    advise_entry_window,
    compute_macro_regime, macro_sizing_multiplier, macro_score_gate_adjustment,
    compute_earnings_risk,
    compute_fundamental_snapshot, canslim_fundamental_override,
    compute_trend_warning,
    compute_multi_horizon_forecast,
    compute_t25_multiframe,
    compute_tplus_recommendation,
    compute_var,
    calibrate_stop_with_var,
)
from ..core.money_flow import (
    compute_multiday_whale_flow, proxy_whale_net_from_daily,
    compute_whale_net_from_pt_deals, calculate_ncvd, resolve_cvd_conflict,
)
from ..core.indicators import sma_with_confidence, get_adaptive_rsi_thresholds, evaluate_rsi_signal
from ..core.bilstm_predictor import BiLSTMPredictor
from ..data.intraday_collector import fetch_intraday_features
from .money_flow_service import MoneyFlowService, sector_flow_lookup
from ..utils.logging import get_logger
import time as _time

log = get_logger("profiler_service")

# ── Module-level macro cache (O1 FIX) ────────────────────────────────────────
# Macro data (USD/VND, bond yield, SBV OMO) changes on a hours-to-days timescale.
# Fetching it per-ticker in a scan of 50+ tickers wastes 50+ redundant HTTP calls.
# Cache is shared across all ProfilerService instances; TTL = 5 minutes.
_MACRO_CACHE: dict = {}   # keys: "result" → MacroResult | None, "ts" → float
_MACRO_TTL = 300.0        # seconds


def _extract_exchange(quote: dict) -> str:
    for key in ("exchange", "Exchange", "market", "Market", "boardId", "board"):
        value = str(quote.get(key, "")).upper()
        if value in ("HOSE", "HNX", "UPCOM"):
            return value
        if value == "MAIN":
            return "HOSE"
    return "HOSE"


class ProfilerService:
    def __init__(self, portfolio_value: float = 300_000_000):
        self.portfolio_value = portfolio_value
        # BiLSTM predictor — loads model once; no-ops if model file absent
        self._bilstm = BiLSTMPredictor()

    def run(self, request: ProfilerRequest) -> TickerProfile:
        """
        Full profiler pipeline for a single ticker.
        Returns a TickerProfile Pydantic model.
        """
        ticker = request.ticker.upper()
        log.info(f"Profiling {ticker} mode={request.mode}")

        # ── 1. Fetch data ──────────────────────────────────────────────────
        try:
            df = fetch_ohlcv(ticker, days=1000)
        except Exception as e:
            log.warning(f"OHLCV fetch failed for {ticker}: {e}")
            return self._error_profile(ticker, str(e))

        if df.empty or len(df) < 30:
            return self._error_profile(ticker, "Insufficient data")

        quote = fetch_quote(ticker)
        exchange = _extract_exchange(quote)

        # ── 2. Compute indicators ──────────────────────────────────────────
        df = compute_indicators(df)

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        close = float(last["close"])
        volume = float(last["volume"])
        avg_vol = float(df["volume"].tail(20).mean())

        # ── 3. Anti-manipulation + Intraday Features ────────────────────
        # Fetch intraday TFI/OBI features (always succeeds — silent fallback on error)
        intraday_feats = fetch_intraday_features(ticker)
        amf_result = run_amf(df, order_book=None, intraday_data=intraday_feats)
        # Inject foreign_net into amf_result details so MFPM can use it for scoring
        amf_result.setdefault("details", {})["foreign_net"] = intraday_feats.get("foreign_net", 0)
        amd_phase = detect_amd_phase(df)
        vqs_result = volume_quality_score(df, order_book=None)
        vqs = float(vqs_result.get("vqs_score", 0.0))

        # ── 4. Money flow (FR-6) ─────────────────────────────────────────
        pt_deals_df = fetch_put_through_deals(ticker, days=5)
        # Use PT deal data when available to upgrade from PROXY_OHLCV → PARTIAL_PROXY,
        # which reduces the Layer 4 confidence penalty (1.0 → 0.5).
        daily_flow_df = compute_whale_net_from_pt_deals(pt_deals_df, df)

        # Merge foreign investor net-flow (fol_net) into daily_flow_df so that
        # SMS component 3 receives real data instead of permanently scoring neutral.
        try:
            fol_df = fetch_foreign_flow(ticker, days=30)
            if (not fol_df.empty
                    and "fol_net" in fol_df.columns
                    and "date" in fol_df.columns
                    and "date" in daily_flow_df.columns):
                fol_df["date"] = pd.to_datetime(fol_df["date"]).dt.date
                daily_flow_df["date"] = pd.to_datetime(daily_flow_df["date"]).dt.date
                daily_flow_df = daily_flow_df.merge(
                    fol_df[["date", "fol_net"]], on="date", how="left"
                )
                daily_flow_df["fol_net"] = daily_flow_df["fol_net"].fillna(0)
        except Exception as _fol_err:
            log.debug(f"FOL merge skipped for {ticker}: {_fol_err}")

        mcvd_detail = compute_multiday_whale_flow(daily_flow_df)

        # ── 4.5. Pre-fetch intraday bars for CVD (feeds into SMS cvd_today) ──────────
        _df_intraday: pd.DataFrame | None = None
        _intraday_source = "NONE"
        _cvd_result: dict = {}
        _cvd_raw: float | None = None
        try:
            # Priority 1: FiinQuant 1m bars with real bu/sd columns
            if _fiin_provider.is_configured():
                _df_intraday = _fiin_provider.fetch_bars(ticker, by="1m", period=60)
                if _df_intraday is not None and not _df_intraday.empty:
                    _intraday_source = "FIINQUANT"
            # Priority 2: DNSE 1m candles
            if _df_intraday is None and _dnse_provider.is_configured():
                _df_intraday = _dnse_provider.fetch_intraday_candles(ticker, resolution="1")
                if _df_intraday is not None and not _df_intraday.empty:
                    _intraday_source = "DNSE"
            # Priority 3: SSI 5m fallback
            if _df_intraday is None:
                _df_5m_pre = fetch_intraday_5m(ticker)
                if _df_5m_pre is not None and not _df_5m_pre.empty:
                    _df_intraday = _df_5m_pre
                    _intraday_source = "SSI_5M"
            if _df_intraday is not None and not _df_intraday.empty:
                _cvd_result = compute_intraday_cvd(_df_intraday)
                _cvd_raw = _cvd_result.get("cvd_raw")
        except Exception as _cvd_pre_err:
            log.debug(f"Pre-fetch CVD skipped for {ticker}: {_cvd_pre_err}")

        sms_result = compute_smart_money_score(
            ticker, df, daily_flow_df, pt_deals_df, None, None, amd_phase,
            cvd_today=_cvd_raw,
            cvd_data_quality=str(_cvd_result.get("data_quality", "NONE")),
        )
        stealth = detect_stealth_accumulation(df, daily_flow_df, amd_phase=amd_phase)
        dist_warning_obj = detect_whale_distribution(df, daily_flow_df)
        dist_warning = dist_warning_obj.get("level", "NONE")

        sms_raw = sms_result.get("sms", 0)
        sms_label = sms_result.get("sms_label", "RETAIL_DRIVEN")

        # ── 5. Patterns ───────────────────────────────────────────────────
        pattern_result = detect_patterns(df)

        # ── 5b. Gap + VWAP + T+2.5 (non-blocking) ────────────────────────
        from ..core.gap_vwap import (
            detect_gaps, compute_vwap_result, compute_vwap_intraday_result,
        )
        from ..core.t25_engine import compute_t25_entry_score

        gap_result  = detect_gaps(df)
        vwap_result = compute_vwap_result(df)
        t25_result  = compute_t25_entry_score(df, pattern_result)

        vwap_intraday_result: dict = {
            "vwap_intraday": None, "vwap_intraday_dev": "AT",
            "vwap_intraday_slope": 0.0,
        }
        try:
            # Re-use already-fetched intraday df from step 4.5; fall back to SSI 5m
            _df_vwap = _df_intraday if _df_intraday is not None else fetch_intraday_5m(ticker)
            vwap_intraday_result = compute_vwap_intraday_result(ticker, _df_vwap)
        except Exception as _intra_err:
            log.debug(f"Intraday VWAP skipped for {ticker}: {_intra_err}")

        # ── 5c. Realtime + Trend Warning + T+2.5 MF (non-blocking) ──────
        rt_data = fetch_realtime(ticker)

        trend_w_result: dict = {"warning": "NONE", "warning_vi": "", "confidence": 0.0, "reasons": []}
        try:
            trend_w_result = compute_trend_warning(df)
        except Exception as _tw_err:
            log.debug(f"Trend warning skipped for {ticker}: {_tw_err}")

        t25_mf_result: dict = {}
        try:
            t25_mf_result = compute_t25_multiframe(df, t25_result, vwap_intraday_result)
        except Exception as _mf_err:
            log.debug(f"T+2.5 multiframe skipped for {ticker}: {_mf_err}")

        # ── 5d. T+ setup recommendation (non-blocking) ────────────────────
        tplus_result: dict = {}
        try:
            tplus_result = compute_tplus_recommendation(
                df, t25_result, pattern_result,
                dist_warning=dist_warning,
                amf_decision=str(amf_result.get("decision", "PASS")),
                amd_phase=str(amd_phase),
            )
        except Exception as _tp_err:
            log.debug(f"T+ recommendation skipped for {ticker}: {_tp_err}")
        # ── 5e. Order Book Imbalance — FiinQuant BidAsk (non-blocking) ──────────────
        _obi_result: dict = {}
        try:
            if _fiin_provider.is_configured():
                _bidask_df = _fiin_provider.fetch_orderbook(ticker)
                if _bidask_df is not None and not _bidask_df.empty:
                    _obi_result = compute_order_book_imbalance(_bidask_df)
        except Exception as _obi_err:
            log.debug(f"OBI skipped for {ticker}: {_obi_err}")
        # ── 6. GMO (HMM + omega) ─────────────────────────────────────────
        hmm_state = detect_hmm_state(df)
        omega = compute_omega(df, None)      # SRS §3.4 gmo_omega

        # ── 6b. Macro regime ─────────────────────────────────────────────
        # [O1 FIX] Cache macro result for 5 min across all tickers in a scan.
        # Macro data (USD/VND, VN10Y bond, SBV OMO) changes on an hours-to-days
        # timescale; fetching it per-ticker wastes 50+ HTTP calls during a scan.
        macro_result = None
        _now = _time.time()
        if _MACRO_CACHE.get("ts") and _now - _MACRO_CACHE["ts"] < _MACRO_TTL:
            macro_result = _MACRO_CACHE.get("result")
            log.debug("Macro cache hit")
        else:
            try:
                usdvnd_df    = fetch_usdvnd(days=60)
                bond_df      = fetch_vn10y_bond_yield(days=60)
                sbv_data     = fetch_sbv_omo_net(days=30)
                macro_result = compute_macro_regime(
                    usdvnd_df=usdvnd_df,
                    bond_yield_df=bond_df,
                    sbv_net_injection_7d=sbv_data.get("net_7d"),
                    sbv_avg_vol_ref=sbv_data.get("avg_ref", 10_000.0),
                )
                _MACRO_CACHE["result"] = macro_result
                _MACRO_CACHE["ts"]     = _now
            except Exception as _macro_err:
                log.debug(f"Macro regime skipped for {ticker}: {_macro_err}")

        # ── 6c. Earnings risk ─────────────────────────────────────────────
        earnings_risk_result = None
        try:
            earnings_df       = fetch_earnings_calendar(ticker, lookforward_days=30)
            earnings_risk_result = compute_earnings_risk(ticker, earnings_df=earnings_df)
        except Exception as _earn_err:
            log.debug(f"Earnings risk skipped for {ticker}: {_earn_err}")

        # ── 6d. Fundamental snapshot ──────────────────────────────────────
        fund_snap = None
        try:
            stmts    = fetch_financial_statements(ticker, quarters=8)
            fol_pct  = float(sms_result.get("fol_pct", 0.0))
            fund_snap = compute_fundamental_snapshot(
                ticker=ticker, statements=stmts, fol_pct=fol_pct
            )
        except Exception as _fund_err:
            log.debug(f"Fundamental snapshot skipped for {ticker}: {_fund_err}")

        # ── 6e. Multi-horizon forecast (uses macro + fund data) ───────────
        fc_result: dict = {}
        try:
            _fc_ctx = {
                "hmm_state":         hmm_state,
                "amd_phase":         amd_phase,
                "macro_regime":      macro_result.macro_regime   if macro_result else "",
                "macro_score":       macro_result.macro_score    if macro_result else None,
                "fundamental_score": fund_snap.fundamental_score if fund_snap    else None,
                "t25_score":         t25_result.get("t25_score"),
                # [VN-FIX V6] Pass ceiling flag so BB bear signal is suppressed on trần
                "rt_at_ceiling":     bool(rt_data.get("rt_at_ceiling", False)),
            }
            fc_result = compute_multi_horizon_forecast(df, _fc_ctx)
        except Exception as _fc_err:
            log.debug(f"Horizon forecast skipped for {ticker}: {_fc_err}")

        # ── 6f. BiLSTM 10-day directional prediction ─────────────────────────
        # Must run before MFPM so the bonus can be applied in compute_mfpm()
        _bilstm_result = self._bilstm.predict(df)

        # ── 7. MFPM scoring ───────────────────────────────────────────────
        try:
            sector_rotation = MoneyFlowService().get_sector_flows()
            sector_flow = sector_flow_lookup(sector_rotation, ticker)
        except Exception:
            sector_flow = sms_result.get("sector_flow", "NEUTRAL")
        sms_result["sector_flow"] = sector_flow
        mfpm_result = compute_mfpm(
            df=df,
            sms_result={
                **sms_result,
                "stealth_detail": stealth,
                "distribution_warning": dist_warning,
                "mcvd_detail": {
                    **mcvd_detail,
                    # [BUG-10 FIX] data_source lives in mcvd_detail, not at
                    # sms_result top level.  Reading from the wrong key always
                    # returned None → fell back to PROXY_OHLCV → harshest penalty
                    # applied even for PARTIAL_PROXY data.
                    "data_source": mcvd_detail.get("data_source", "PROXY_OHLCV"),
                },
                # Pass BiLSTM signal so MFPM can apply directional bonus
                "bilstm_10d_signal":     _bilstm_result.get("signal",     "NO_MODEL"),
                "bilstm_10d_confidence": _bilstm_result.get("confidence", "NONE"),
            },
            amf_result=amf_result,
            pattern_result=pattern_result,
            hmm_state=hmm_state,
            amd_phase=amd_phase,
            sector_flow=sector_flow,
            horizons=request.horizons or [2, 3, 5, 7, 10],
            macro_result=macro_result,
            earnings_risk=earnings_risk_result,
            fundamental_snapshot=fund_snap,
        )

        action = mfpm_result["action"]
        confidence = mfpm_result["confidence"]
        signal_mode = mfpm_result["signal_mode"]
        entry = mfpm_result["entry"]
        sl = mfpm_result["sl"]
        tp1 = mfpm_result["tp1"]
        tp2 = mfpm_result["tp2"]
        rr = mfpm_result["rr_ratio"]
        mc_prob = mfpm_result["mc_win_prob"]

        # ── 8. Position sizing ────────────────────────────────────────────
        macro_mult = macro_sizing_multiplier(macro_result) if macro_result else 1.0
        sizing = compute_position_size(
            portfolio_value=self.portfolio_value,
            entry=entry,
            sl=sl,
            win_prob=mc_prob,
            rr=rr,
            macro_multiplier=macro_mult,
        )

        # ── 9. Execution advisory ─────────────────────────────────────────
        exec_adv = advise_entry_window(action, signal_mode, confidence, close, entry)

        # ── 10. NLP text ──────────────────────────────────────────────────
        advisory_vi = generate_signal_text(
            ticker=ticker, action=action, confidence=confidence,
            mfpm_score=mfpm_result["mfpm_score"],
            mode_w_score=mfpm_result["mode_w_score"],
            sms_raw=sms_raw, hmm_state=hmm_state,
            signal_mode=signal_mode,
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, rr=rr, mc_prob=mc_prob,
            distribution_warning=dist_warning,
            mode_w_conditions_failed=mfpm_result.get("mode_w_failed_conditions", []),
            mode_a_score=mfpm_result.get("mode_a_score", 0),
            mode_b_score=mfpm_result.get("mode_b_score", 0),
            amd_phase=mfpm_result.get("amd_phase", "RANGING"),
            best_pattern=pattern_result.get("best_pattern", "NONE") if pattern_result else "NONE",
            amf_decision=amf_result.get("decision", "PASS") if amf_result else "PASS",
            stealth_accum=bool((stealth or {}).get("detected", False)),
            stealth_confidence=(stealth or {}).get("confidence", "LOW"),
            mcvd_trend=(mcvd_detail or {}).get("mcvd_trend", "FLAT"),
            mcvd_5d=float((mcvd_detail or {}).get("mcvd_5d", 0.0)),
            pt_net_5d=float(sms_result.get("pt_net_5d", 0.0)),
            rsi14=float(last.get("RSI14", 50.0)),
            close=close,
            lang="vi",
        )

        # ── 11. Build TickerProfile ───────────────────────────────────────
        latest_close = close
        sma3  = float(last.get("SMA3",  0))
        sma5  = float(last.get("SMA5",  0))
        sma7  = float(last.get("SMA7",  0))
        sma10 = float(last.get("SMA10", 0))
        sma20 = float(last.get("SMA20", 0))
        sma50 = float(last.get("SMA50", 0))
        sma200_raw, sma200_conf = sma_with_confidence(df["close"], 200)
        sma200 = sma200_raw if sma200_raw is not None else float(last.get("SMA200", 0) or 0)
        ema50  = float(last.get("EMA50",  0))
        ema200 = float(last.get("EMA200", 0))
        rsi14 = float(last.get("RSI14", 50))
        atr14 = float(last.get("ATR14", 0))
        obv_val = float(last.get("OBV", 0))

        # ── 8b. ATR-based position sizing (Phase II) ─────────────────────
        _atr_sizing = compute_atr_position_size(
            entry_price=entry,
            atr14=atr14,
            portfolio_value=self.portfolio_value,
            amf_decision=amf_result.get("decision", "PASS"),
        )

        # ── 8c. GJR-GARCH VaR / CVaR (Phase III) ────────────────────────
        _risk_model = compute_var(df)
        _stop_loss_var = calibrate_stop_with_var(
            entry_price=entry,
            atr_stop=float(_atr_sizing["atr_stop_price"]),
            var_99=float(_risk_model.var_99),
        )

        # [BUG-2 FIX] MACD = EMA12 - EMA26 (standard formula).
        # Using EMA9-EMA21 was wrong: EMA9 is the signal line, not MACD fast.
        # Use the already-computed MACD_line column from indicators.py.
        macd = float(last.get("MACD_line", 0.0))

        # ── 11a. Derived signal enrichments ─────────────────────────────────
        # NCVD: normalize raw M-CVD by ADTV so cross-ticker comparison is meaningful
        _adtv = float(df["volume"].tail(20).mean())
        _ncvd_5d  = calculate_ncvd(mcvd_detail.get("mcvd_5d",  0), _adtv, window_days=5)
        _ncvd_20d = calculate_ncvd(mcvd_detail.get("mcvd_20d", 0), _adtv, window_days=20)

        # CVD conflict resolution (5d trend vs 20d trend with AMD override)
        _cvd_conflict = resolve_cvd_conflict(
            cvd_5d_trend=mcvd_detail.get("mcvd_trend", "FLAT"),   # 5d slope trend
            cvd_20d_trend=(
                "UP"   if mcvd_detail.get("mcvd_20d", 0) > 0 else
                "DOWN" if mcvd_detail.get("mcvd_20d", 0) < 0 else "FLAT"
            ),
            amd_phase=amd_phase,
        )

        # Adaptive RSI: map HMM state + sector to regime-adjusted thresholds
        _hmm_regime = hmm_state  # STEADY_BULL | TRANSITIONAL | STEADY_BEAR
        _sector_tag = sms_result.get("sector", "GENERAL")
        _rsi_signal = evaluate_rsi_signal(rsi14, regime=_hmm_regime, sector=_sector_tag)

        profile = TickerProfile(
            # Identity
            ticker=ticker,
            exchange=exchange,
            sector=sms_result.get("sector", ""),
            last_updated=datetime.now().isoformat(),
            # Signal output
            action=action,
            confidence=confidence,
            signal_mode=signal_mode,
            mfpm_score=mfpm_result["mfpm_score"],
            mode_w_score=mfpm_result["mode_w_score"],
            mc_win_prob=mc_prob,
            # Entry/Exit
            entry_price=entry,
            stop_loss=sl,
            sl_pct=mfpm_result["sl_pct"],
            tp1=tp1,
            tp2=tp2,
            rr_ratio=rr,
            # Traditional indicators
            close=latest_close,
            volume=volume,
            avg_volume_20d=avg_vol,
            sma3=sma3,
            sma5=sma5,
            sma7=sma7,
            sma10=sma10,
            sma20=sma20,
            sma50=sma50,
            sma200=sma200,
            ema50=ema50,
            ema200=ema200,
            rsi14=rsi14,
            atr14=atr14,
            obv=obv_val,
            macd=macd,
            # FR-6 fields
            sms_raw=sms_raw,
            sms_label=sms_label,
            mcvd_5d=mcvd_detail.get("mcvd_5d", 0),
            mcvd_20d=mcvd_detail.get("mcvd_20d", 0),
            mcvd_trend=mcvd_detail.get("mcvd_trend", "FLAT"),
            stealth_accum=bool(stealth.get("detected")),
            stealth_confidence=stealth.get("confidence", "LOW"),
            distribution_warning=dist_warning,
            pt_net_5d=sms_result.get("pt_net_5d", 0),
            pt_ratio_5d=sms_result.get("pt_ratio_5d", 0.0),
            # Explanation
            amd_phase=amd_phase,
            hmm_state=hmm_state,
            vqs=vqs,
            amf_decision=amf_result.get("decision", "PASS"),
            amf_flags=amf_result.get("flags", []),
            best_pattern=pattern_result.get("best_pattern", "NONE"),
            gmo_omega=float(omega),
            sector_flow=sms_result.get("sector_flow", "NEUTRAL"),
            fol_net_5d=int(sms_result.get("fol_net_5d", 0)),
            whale_pct_vol=float(sms_result.get("whale_pct_vol", 0.0)),
            sizing_pct=sizing.get("size_pct", 0.0),
            sizing_shares=sizing.get("shares", 0),
            # ATR-based position sizing (Phase II)
            atr_position_shares = _atr_sizing["atr_position_shares"],
            atr_stop_price      = _atr_sizing["atr_stop_price"],
            atr_stop_distance   = _atr_sizing["atr_stop_distance"],
            atr_position_value  = _atr_sizing["atr_position_value"],
            atr_risk_amount     = _atr_sizing["atr_risk_amount"],
            atr_risk_pct_actual = _atr_sizing["atr_risk_pct_actual"],
            atr_size_pct        = _atr_sizing["atr_size_pct"],
            advisory_text=advisory_vi,
            entry_window=exec_adv.get("window", "—"),
            horizons=mfpm_result.get("horizons", []),
            # Phase 2 — Macro
            macro_score      = macro_result.macro_score      if macro_result else None,
            macro_regime     = macro_result.macro_regime      if macro_result else "",
            macro_confidence = macro_result.macro_confidence  if macro_result else "",
            macro_staleness_days = macro_result.macro_staleness_days if macro_result else 0,
            # Phase 2 — Earnings
            earnings_risk    = earnings_risk_result.rollover_risk.value if earnings_risk_result else "SAFE",
            days_to_earnings = earnings_risk_result.days_to_next_event if earnings_risk_result else None,
            next_earnings_date = str(earnings_risk_result.next_pub_date) if (earnings_risk_result and earnings_risk_result.next_pub_date) else "",
            # Phase 3 — Fundamentals
            fundamental_score  = fund_snap.fundamental_score  if fund_snap else None,
            eps_growth_yoy     = fund_snap.eps_growth_yoy     if fund_snap else None,
            revenue_growth_yoy = fund_snap.revenue_growth_yoy if fund_snap else None,
            roe                = fund_snap.roe                 if fund_snap else None,
            debt_to_equity     = fund_snap.debt_to_equity      if fund_snap else None,
            # Gap Analysis
            gap_pct            = gap_result.get("gap_pct", 0.0),
            gap_type           = gap_result.get("gap_type", "NO_GAP"),
            avg_gap_pct        = gap_result.get("avg_gap_pct", 0.0),
            gap_fill_pct       = gap_result.get("gap_fill_pct", 0.0),
            # VWAP Daily
            vwap_daily_val     = float(vwap_result.get("vwap") or 0.0),
            price_vs_vwap_pct  = vwap_result.get("price_vs_vwap_pct", 0.0),
            vwap_dev           = vwap_result.get("vwap_dev", "AT"),
            # VWAP Intraday
            vwap_intraday      = vwap_intraday_result.get("vwap_intraday"),
            vwap_intraday_dev  = vwap_intraday_result.get("vwap_intraday_dev", "AT"),
            vwap_intraday_slope= vwap_intraday_result.get("vwap_intraday_slope", 0.0),
            # T+2.5
            t25_score          = t25_result.get("t25_score"),
            t25_signal         = t25_result.get("t25_signal", ""),
            t25_momo_score     = t25_result.get("t25_momo_score", 0.0),
            t25_struct_score   = t25_result.get("t25_struct_score", 0.0),
            t25_conf_score     = t25_result.get("t25_conf_score", 0.0),
            t25_confirms       = t25_result.get("t25_confirms", []),
            # MFPM decomposition (SHAP)
            mode_a_score       = mfpm_result.get("mode_a_score", 0),
            mode_b_score       = mfpm_result.get("mode_b_score", 0),
            sms_components     = sms_result.get("components", {}),
            # Real-time price header
            rt_price           = rt_data.get("rt_price"),
            rt_pct_change      = rt_data.get("rt_pct_change", 0.0),
            rt_reference       = rt_data.get("rt_reference"),
            rt_ceiling         = rt_data.get("rt_ceiling"),
            rt_floor           = rt_data.get("rt_floor"),
            rt_at_ceiling      = bool(rt_data.get("rt_at_ceiling", False)),
            rt_at_floor        = bool(rt_data.get("rt_at_floor", False)),
            rt_volume_today    = float(rt_data.get("rt_volume_today", 0.0)),
            # Trend Warning
            trend_warning      = trend_w_result.get("warning",    "NONE"),
            trend_warning_vi   = trend_w_result.get("warning_vi", ""),
            trend_warning_conf = trend_w_result.get("confidence",  0.0),
            trend_warning_reasons = trend_w_result.get("reasons",  []),
            # Multi-horizon forecast
            fc_short_vote      = fc_result.get("short_vote",    ""),
            fc_short_conf      = fc_result.get("short_conf",     0.0),
            fc_short_reasons   = fc_result.get("short_reasons",  []),
            fc_mid_vote        = fc_result.get("mid_vote",       ""),
            fc_mid_conf        = fc_result.get("mid_conf",        0.0),
            fc_mid_reasons     = fc_result.get("mid_reasons",     []),
            fc_long_vote       = fc_result.get("long_vote",      ""),
            fc_long_conf       = fc_result.get("long_conf",       0.0),
            fc_long_reasons    = fc_result.get("long_reasons",    []),
            fc_overall_vote    = fc_result.get("overall_vote",   ""),
            fc_overall_conf    = fc_result.get("overall_conf",    0.0),
            # T+2.5 Multi-frame
            t25_morning_score  = t25_mf_result.get("morning_score",   0.0),
            t25_midday_score   = t25_mf_result.get("midday_score",    0.0),
            t25_afternoon_score= t25_mf_result.get("afternoon_score", 0.0),
            t25_best_window    = t25_mf_result.get("best_window",     ""),
            t25_mf_reasons     = t25_mf_result.get("mf_reasons",      []),
            # T+ Setup Recommendation
            tplus_setup          = tplus_result.get("setup_type",      "T_NO_SETUP"),
            tplus_setup_vi       = tplus_result.get("setup_vi",        ""),
            tplus_entry_trigger  = tplus_result.get("entry_trigger",   ""),
            tplus_entry_low      = tplus_result.get("entry_zone_low",  0.0),
            tplus_entry_high     = tplus_result.get("entry_zone_high", 0.0),
            tplus_target_t25     = tplus_result.get("target_t25",      0.0),
            tplus_target_t5      = tplus_result.get("target_t5",       0.0),
            tplus_stop           = tplus_result.get("stop_loss",       0.0),
            tplus_rr             = tplus_result.get("rr_ratio",        0.0),
            tplus_confidence     = tplus_result.get("confidence",      0.0),
            tplus_session        = tplus_result.get("session",         ""),
            tplus_session_vi     = tplus_result.get("session_vi",      ""),
            tplus_verdict        = tplus_result.get("verdict",         "THEO_DOI"),
            tplus_verdict_vi     = tplus_result.get("verdict_vi",      ""),
            tplus_reasons        = tplus_result.get("reasons",         []),
            tplus_risks          = tplus_result.get("risks",           []),
            # Intraday CVD & OBI
            cvd_signal              = _cvd_result.get("cvd_signal",              "NEUTRAL"),
            cvd_divergence          = _cvd_result.get("cvd_divergence",          "NONE"),
            cvd_buying_pressure_pct = _cvd_result.get("buying_pressure_pct",     50.0),
            cvd_score               = _cvd_result.get("cvd_score",               5.0),
            cvd_data_quality        = _cvd_result.get("data_quality",            "NONE"),
            obi_pct                 = _obi_result.get("obi_pct",                 0.0),
            obi_signal              = _obi_result.get("obi_signal",              "BALANCED"),
            data_source_intraday    = _intraday_source,
            # NCVD (normalized M-CVD)
            ncvd_5d                 = _ncvd_5d["ncvd"],
            ncvd_5d_label           = _ncvd_5d["label"],
            ncvd_20d                = _ncvd_20d["ncvd"],
            ncvd_20d_label          = _ncvd_20d["label"],
            # CVD conflict resolution
            cvd_conflict_pattern    = _cvd_conflict["pattern"],
            cvd_conflict_action     = _cvd_conflict["action"],
            cvd_conflict_confidence = _cvd_conflict["confidence"],
            # SMA200 data quality
            sma200_confidence       = sma200_conf,
            # Adaptive RSI
            rsi_label               = _rsi_signal["label"],
            rsi_action_hint         = _rsi_signal["action_hint"],
            rsi_ob_threshold        = _rsi_signal["overbought"],
            # AMF Wash Sale Directionality
            amf_wash_side           = amf_result.get("wash_side", "NONE"),
            amf_tfi                 = float(intraday_feats.get("tfi", 0.0)),
            amf_obi                 = float(intraday_feats.get("obi_l3", 0.0)),
            amf_obi_reconstructed   = float(intraday_feats.get("obi_reconstructed", 0.0)),
            amf_foreign_net         = int(intraday_feats.get("foreign_net", 0)),
            amf_mcvd                = int(intraday_feats.get("mcvd", 0)),
            # BiLSTM 10-day directional signal
            bilstm_10d_signal       = _bilstm_result["signal"],
            bilstm_10d_up_prob      = float(_bilstm_result["up_prob"]),
            bilstm_10d_confidence   = _bilstm_result["confidence"],
            # GJR-GARCH Risk Model (Phase III)
            var_95                  = float(_risk_model.var_95),
            var_99                  = float(_risk_model.var_99),
            cvar_95                 = float(_risk_model.cvar_95),
            tail_regime             = _risk_model.tail_regime,
            var_model               = _risk_model.var_model,
            var_cond_vol            = float(_risk_model.cond_vol),
            stop_loss_var           = float(_stop_loss_var),
        )

        # ── 12. Audit log ─────────────────────────────────────────────────
        vwap_daily = float(last.get("VWAP_daily", 0))
        fvgs = (pattern_result or {}).get("fvgs", [])
        cache.put_audit({
            "event_type": "PROFILE",
            "ticker": ticker,
            "action": action,
            "mfpm_score": mfpm_result["mfpm_score"],
            "sms_raw": sms_raw,
            "confidence": confidence,
            "payload": {
                # Score breakdown
                "mode_a_score":  mfpm_result.get("mode_a_score", 0),
                "mode_b_score":  mfpm_result.get("mode_b_score", 0),
                "mode_w_score":  mfpm_result.get("mode_w_score", 0),
                "mc_prob":       round(mc_prob, 3),
                # Signal context
                "signal_mode":   signal_mode,
                "amd_phase":     amd_phase,
                "hmm_state":     hmm_state,
                "amf_decision":  amf_result.get("decision", "PASS"),
                "amf_flags":     amf_result.get("flags", []),
                "best_pattern":  (pattern_result or {}).get("best_pattern", "NONE"),
                "stealth_accum": bool(stealth.get("detected")),
                "stealth_conf":  stealth.get("confidence", "LOW"),
                "dist_warning":  dist_warning,
                # Levels
                "close":         close,
                "entry":         entry,
                "sl":            sl,
                "tp1":           tp1,
                "tp2":           tp2,
                "rr":            round(rr, 2),
                # Money flow
                "mcvd_trend":    mcvd_detail.get("mcvd_trend", "FLAT"),
                "mcvd_5d":       mcvd_detail.get("mcvd_5d", 0),
                "pt_net_5d":     sms_result.get("pt_net_5d", 0),
                "sector_flow":   sms_result.get("sector_flow", "NEUTRAL"),
                "whale_pct_vol": float(sms_result.get("whale_pct_vol", 0.0)),
                # Technical indicators
                "rsi14":         float(last.get("RSI14", 50)),
                "sma20":         float(last.get("SMA20", 0)),
                "sma50":         float(last.get("SMA50", 0)),
                "atr14":         float(last.get("ATR14", 0)),
                "vwap_daily":    vwap_daily,
                "obv":           float(last.get("OBV", 0)),
                "vqs":           float(vqs),
                "gmo_omega":     float(omega),
                # FVG zones (last 3)
                "fvg_zones":     fvgs[-3:] if fvgs else [],
                # Sizing
                "sizing_pct":    sizing.get("size_pct", 0.0),
                "sector":        sms_result.get("sector", ""),
            },
        })

        return profile

    def _error_profile(self, ticker: str, error: str) -> TickerProfile:
        """Return a TickerProfile indicating an error."""
        cache.put_audit({
            "event_type": "ERROR",
            "ticker": ticker,
            "rejected_reason": error,
        })
        return TickerProfile(
            ticker=ticker,
            action="ERROR",
            advisory_text=f"Lỗi xử lý {ticker}: {error}",
            last_updated=datetime.now().isoformat(),
        )
