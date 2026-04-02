"""Profiler Service — orchestrates full FR-2 ticker profile pipeline."""
from __future__ import annotations

import traceback
from datetime import datetime

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_foreign_flow, fetch_put_through_deals, fetch_quote
from ..data.fetcher import fetch_usdvnd, fetch_vn10y_bond_yield, fetch_sbv_omo_net
from ..data.fetcher import fetch_earnings_calendar, fetch_financial_statements
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
    generate_signal_text,
    advise_entry_window,
    compute_macro_regime, macro_sizing_multiplier, macro_score_gate_adjustment,
    compute_earnings_risk,
    compute_fundamental_snapshot, canslim_fundamental_override,
)
from ..core.money_flow import compute_multiday_whale_flow, proxy_whale_net_from_daily, compute_whale_net_from_pt_deals
from .money_flow_service import MoneyFlowService, sector_flow_lookup
from ..utils.logging import get_logger

log = get_logger("profiler_service")


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

    def run(self, request: ProfilerRequest) -> TickerProfile:
        """
        Full profiler pipeline for a single ticker.
        Returns a TickerProfile Pydantic model.
        """
        ticker = request.ticker.upper()
        log.info(f"Profiling {ticker} mode={request.mode}")

        # ── 1. Fetch data ──────────────────────────────────────────────────
        try:
            df = fetch_ohlcv(ticker, days=260)
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

        # ── 3. Anti-manipulation ──────────────────────────────────────────
        amf_result = run_amf(df, order_book=None)
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
        sms_result = compute_smart_money_score(
            ticker, df, daily_flow_df, pt_deals_df, None, None, amd_phase
        )
        stealth = detect_stealth_accumulation(df, daily_flow_df, amd_phase=amd_phase)
        dist_warning_obj = detect_whale_distribution(df, daily_flow_df)
        dist_warning = dist_warning_obj.get("level", "NONE")

        sms_raw = sms_result.get("sms", 0)
        sms_label = sms_result.get("sms_label", "RETAIL_DRIVEN")

        # ── 5. Patterns ───────────────────────────────────────────────────
        pattern_result = detect_patterns(df)

        # ── 6. GMO (HMM + omega) ─────────────────────────────────────────
        hmm_state = detect_hmm_state(df)
        omega = compute_omega(df, None)      # SRS §3.4 gmo_omega

        # ── 6b. Macro regime ─────────────────────────────────────────────
        # Fetch once; use cached result if fresh from same scan batch
        macro_result = None
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
                    "data_source": sms_result.get("data_source", "PROXY_OHLCV"),
                },
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
        sma20 = float(last.get("SMA20", 0))
        sma50 = float(last.get("SMA50", 0))
        sma200 = float(last.get("SMA200", 0))
        rsi14 = float(last.get("RSI14", 50))
        atr14 = float(last.get("ATR14", 0))
        obv_val = float(last.get("OBV", 0))
        macd = float(last.get("EMA9", 0)) - float(last.get("EMA21", 0))

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
            sma20=sma20,
            sma50=sma50,
            sma200=sma200,
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
