"""Profiler Service — orchestrates full FR-2 ticker profile pipeline."""
from __future__ import annotations

import traceback
from datetime import datetime

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_foreign_flow
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
)
from ..core.money_flow import compute_multiday_whale_flow, proxy_whale_net_from_daily
from ..utils.logging import get_logger

log = get_logger("profiler_service")


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
        daily_flow_df = proxy_whale_net_from_daily(df)
        mcvd_detail = compute_multiday_whale_flow(daily_flow_df)
        sms_result = compute_smart_money_score(ticker, df, daily_flow_df, None, None, amd_phase)
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

        # ── 7. MFPM scoring ───────────────────────────────────────────────
        sector_flow = sms_result.get("sector_flow", "NEUTRAL")
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
        sizing = compute_position_size(
            portfolio_value=self.portfolio_value,
            entry=entry,
            sl=sl,
            win_prob=mc_prob,
            rr=rr,
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
            exchange="HOSE",
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
        )

        # ── 12. Audit log ─────────────────────────────────────────────────
        cache.put_audit({
            "event_type": "PROFILE",
            "ticker": ticker,
            "action": action,
            "mfpm_score": mfpm_result["mfpm_score"],
            "sms_raw": sms_raw,
            "confidence": confidence,
        })

        return profile

    def _error_profile(self, ticker: str, reason: str) -> TickerProfile:
        return TickerProfile(
            ticker=ticker, exchange="HOSE", sector="", last_updated=datetime.now().isoformat(),
            action="NO_ACTION", confidence="—", signal_mode="—",
            mfpm_score=0, mode_w_score=0, mc_win_prob=0.0,
            entry_price=0, stop_loss=0, sl_pct=0, tp1=0, tp2=0, rr_ratio=0,
            close=0, volume=0, avg_volume_20d=0,
            sma20=0, sma50=0, sma200=0, rsi14=0, atr14=0, obv=0, macd=0,
            sms_raw=0, sms_label="RETAIL_DRIVEN",
            mcvd_5d=0, mcvd_20d=0, mcvd_trend="FLAT",
            stealth_accum=False, stealth_confidence="LOW",
            distribution_warning="NONE",
            amd_phase="RANGING", hmm_state="TRANSITIONAL",
            gmo_omega=0.0, vqs=0.0, amf_decision="PASS", amf_flags=[],
            best_pattern="NONE", sector_flow="NEUTRAL",
            fol_net_5d=0, whale_pct_vol=0.0,
            sizing_pct=0.0, sizing_shares=0,
            advisory_text=f"Error: {reason}",
            entry_window="—", horizons=[],
        )
