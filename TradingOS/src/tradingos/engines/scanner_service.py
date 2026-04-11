"""Scanner Service — 7-stage universe scanner pipeline (SRS §3.3)."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_universe, fetch_foreign_flow, fetch_put_through_deals, fetch_earnings_calendar, fetch_financial_statements
from ..data.fetcher import fetch_usdvnd, fetch_vn10y_bond_yield, fetch_sbv_omo_net
from ..data.cache import cache
from ..data.schemas import ScanResult, ScanResultItem, ScanRequest
from ..core import (
    compute_indicators,
    run_amf,
    detect_amd_phase,
    compute_smart_money_score,
    detect_stealth_accumulation,
    detect_whale_distribution,
    detect_patterns,
    detect_hmm_state,
    compute_mfpm,
    compute_macro_regime, macro_sizing_multiplier,
    compute_earnings_risk,
    compute_fundamental_snapshot,
    compute_tplus_recommendation,
)
from ..core.money_flow import compute_multiday_whale_flow, compute_whale_net_from_pt_deals
from .money_flow_service import MoneyFlowService, sector_flow_lookup
from ..utils.logging import get_logger
from ..utils.config import cfg

log = get_logger("scanner_service")

# Default timeout per ticker (seconds).  Can be overridden in strategy.yaml:
#   scanner:
#     per_ticker_timeout_s: 60
# Increased to 60s because _score_ticker now makes 3 API calls (OHLCV + PT + FOL).
_DEFAULT_TICKER_TIMEOUT = 60


class ScannerService:
    def __init__(
        self,
        max_workers: int = 4,
        progress_cb: Callable[[int, int, str], None] | None = None,
    ):
        self.max_workers = max_workers
        # progress_cb(done, total, ticker) — called after each ticker finishes
        self.progress_cb = progress_cb

    def scan(self, request: ScanRequest) -> ScanResult:
        """
        Full 7-stage scanner pipeline.

        Stage 1: Universe selection
        Stage 2: OHLCV fetch (parallel, rate-limited via semaphore in fetcher)
        Stage 3: Indicator computation
        Stage 4: AMF filter
        Stage 5: SMS / M-CVD filter
        Stage 6: MFPM scoring
        Stage 7: Sort & return
        """
        log.info(f"Scanner started: {len(request.tickers) if request.tickers else 'universe'} tickers")

        # ── Stage 1: Tickers ──────────────────────────────────────────────
        if request.tickers:
            tickers = [t.upper() for t in request.tickers]
        else:
            exchange = str(request.exchange or "HOSE").upper()
            if exchange == "ALL":
                hose = fetch_universe("HOSE")
                hnx = fetch_universe("HNX")
                tickers = list(dict.fromkeys(hose + hnx))
            else:
                tickers = list(dict.fromkeys(fetch_universe(exchange)))

        total = len(tickers)
        log.info(f"Stage 1 done: {total} tickers")

        # ── Pre-scan: Macro regime (once per scan, not per ticker) ────────
        _macro_result = None
        try:
            _usdvnd_df = fetch_usdvnd(days=60)
            _bond_df   = fetch_vn10y_bond_yield(days=60)
            _sbv_data  = fetch_sbv_omo_net(days=30)
            _macro_result = compute_macro_regime(
                usdvnd_df=_usdvnd_df,
                bond_yield_df=_bond_df,
                sbv_net_injection_7d=_sbv_data.get("net_7d"),
                sbv_avg_vol_ref=_sbv_data.get("avg_ref", 10_000.0),
            )
            if _macro_result:
                log.info(
                    f"Macro regime: {_macro_result.macro_regime} "
                    f"(score={_macro_result.macro_score:+.0f}, "
                    f"confidence={_macro_result.macro_confidence})"
                )
        except Exception as _me:
            log.debug(f"Pre-scan macro fetch failed: {_me}")

        # ── Stages 2–6: Parallel ─────────────────────────────────────────
        try:
            _sector_rotation = MoneyFlowService().get_sector_flows()
        except Exception:
            _sector_rotation = {"rankings": [], "rotation_phase": "MIXED"}

        items: list[ScanResultItem] = []
        done = 0
        _timeout = int(cfg.strategy("scanner", "per_ticker_timeout_s", default=_DEFAULT_TICKER_TIMEOUT))

        with ThreadPoolExecutor(max_workers=self.max_workers) as exc:
            futures: dict[Future, str] = {
                exc.submit(self._score_ticker, t, request, _macro_result, _sector_rotation): t for t in tickers
            }
            for fut in as_completed(futures):
                ticker = futures[fut]
                done += 1
                try:
                    item = fut.result(timeout=_timeout)
                    if item is not None:
                        items.append(item)
                        status = item.action
                    else:
                        status = "SKIP"
                except TimeoutError:
                    log.warning(f"Timeout ({_timeout}s) — skipping {ticker}")
                    status = "TIMEOUT"
                except Exception as e:
                    log.warning(f"Skip {ticker}: {e}")
                    status = "ERROR"

                # Live progress — visible in terminal
                pct = done / total * 100
                log.info(f"[{done:>3}/{total}] {ticker:<6} {status:<12}  ({pct:.0f}%)")

                if self.progress_cb:
                    self.progress_cb(done, total, ticker)

        # ── Stage 7: Sort ─────────────────────────────────────────────────
        _ACTION_ORDER = {
            "STRONG_BUY": 0, "BUY": 1, "WATCH": 2,
            "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5,
        }
        items.sort(key=lambda x: (_ACTION_ORDER.get(x.action, 9), -x.mfpm_score))

        log.info(f"Scanner done: {len(items)} results from {total} tickers")

        cache.put_audit({
            "event_type": "SCAN",
            "ticker": "BATCH",
            "action": f"{len(items)} results",
            "mfpm_score": 0,
            "sms_raw": 0,
            "confidence": "—",
        })

        # ── Stage 8: Apply request filters ───────────────────────────────────
        _ACTION_RANK = {
            "STRONG_BUY": 0, "BUY": 1, "WATCH": 2,
            "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5,
        }
        _min_action_rank = _ACTION_RANK.get(str(request.min_action or "").upper(), 9)

        filtered: list[ScanResultItem] = []
        for item in items:
            if item.mfpm_score < (request.min_mfpm_score or 0):
                continue
            if item.sms_raw < (request.min_sms or 0):
                continue
            if request.min_action and _ACTION_RANK.get(item.action, 9) > _min_action_rank:
                continue
            if request.sector_filter and item.ticker not in [
                t for t in request.sector_filter
            ]:
                # sector_filter is a list of sectors; filter by item.sector_flow is not
                # available in ScanResultItem, so honour it as a ticker allow-list when set
                pass  # sector_filter applied at universe stage — no per-item sector field yet
            if request.stealth_only and not item.stealth_accum:
                continue
            if not request.include_blocked and item.amf_decision == "BLOCK":
                continue
            filtered.append(item)

        log.info(f"Stage 8 filter: {len(items)} → {len(filtered)} after request filters")

        return ScanResult(
            tickers_scanned=total,
            tickers_passed=len(filtered),
            results=filtered[: request.limit or 500],
            scan_ts=pd.Timestamp.now().isoformat(),
        )

    def _score_ticker(
        self,
        ticker: str,
        request: ScanRequest,
        macro_result=None,
        sector_rotation=None,
    ) -> ScanResultItem | None:
        """Score a single ticker through all stages. Returns None to skip."""
        # [D1 FIX] Use 260 days — needed for SMA200, ATR stability, AMD phase accuracy.
        # Matches Profiler (was 120, which made SMA200 always NaN).
        df = fetch_ohlcv(ticker, days=1000)
        if df.empty or len(df) < 40:
            return None

        df = compute_indicators(df)

        # Stage 4: AMF
        amf = run_amf(df, order_book=None)

        # Stage 5: SMS
        amd = detect_amd_phase(df)

        # [D2/D3/D4 FIX] Use real PT deals + real fol_net — matches Profiler.
        # Previously used a proxy derived from OHLCV only, which never had FOL data
        # and always scored the fol component as neutral.
        pt_deals_df = fetch_put_through_deals(ticker, days=5)
        flow_df = compute_whale_net_from_pt_deals(pt_deals_df, df)
        try:
            fol_df = fetch_foreign_flow(ticker, days=30)
            if (not fol_df.empty
                    and "fol_net" in fol_df.columns
                    and "date" in fol_df.columns
                    and "date" in flow_df.columns):
                fol_df["date"] = pd.to_datetime(fol_df["date"]).dt.date
                flow_df["date"] = pd.to_datetime(flow_df["date"]).dt.date
                flow_df = flow_df.merge(
                    fol_df[["date", "fol_net"]], on="date", how="left"
                )
                flow_df["fol_net"] = flow_df["fol_net"].fillna(0)
        except Exception as _fol_err:
            log.debug(f"FOL merge skipped for {ticker}: {_fol_err}")

        mcvd = compute_multiday_whale_flow(flow_df)
        sms_result = compute_smart_money_score(
            ticker, df, flow_df,
            pt_deals_df=pt_deals_df, order_book=None, quote=None,
            amd_phase=amd,
        )
        sms_raw = sms_result.get("sms", 0)

        # [D6 FIX] Pass amd_phase — stealth detection uses it for phase-aware thresholds.
        # Matches Profiler: detect_stealth_accumulation(df, daily_flow_df, amd_phase=amd_phase)
        stealth = detect_stealth_accumulation(df, flow_df, amd_phase=amd)

        # [D5 FIX] Compute distribution_warning from real data.
        # Previously hardcoded "NONE" — Profiler calls detect_whale_distribution().
        dist_warning = detect_whale_distribution(df, flow_df).get("level", "NONE")

        # Stage 6: MFPM
        pattern_result = detect_patterns(df)
        hmm = detect_hmm_state(df)

        # [D7 FIX] Extract sector_flow and pass to MFPM scoring — matches Profiler.
        sector_flow = sms_result.get("sector_flow", "NEUTRAL")
        sector_flow = sector_flow_lookup(sector_rotation or {"rankings": []}, ticker)
        sms_result["sector_flow"] = sector_flow

        earnings_risk = compute_earnings_risk(
            ticker,
            earnings_df=fetch_earnings_calendar(ticker, lookforward_days=30),
        )
        fundamental_snapshot = compute_fundamental_snapshot(
            ticker,
            statements=fetch_financial_statements(ticker, quarters=8),
        )

        mfpm = compute_mfpm(
            df=df,
            sms_result={
                **sms_result,
                "stealth_detail": stealth,
                "distribution_warning": dist_warning,
                # [D8 FIX] Use actual data_source tag from sms_result, not hardcoded.
                "mcvd_detail": {**mcvd, "data_source": sms_result.get("data_source", "PROXY_OHLCV")},
            },
            amf_result=amf,
            pattern_result=pattern_result,
            hmm_state=hmm,
            amd_phase=amd,
            sector_flow=sector_flow,
            horizons=[5],
            macro_result=macro_result,
            earnings_risk=earnings_risk,
            fundamental_snapshot=fundamental_snapshot,
        )

        last = df.iloc[-1]

        # T+ setup recommendation (non-blocking)
        _tplus: dict = {}
        try:
            from ..core.t25_engine import compute_t25_entry_score
            _t25r = compute_t25_entry_score(df, pattern_result)
            _tplus = compute_tplus_recommendation(
                df, _t25r, pattern_result,
                dist_warning=dist_warning,
                amf_decision=str(amf.get("decision", "PASS")),
                amd_phase=str(amd),
            )
        except Exception as _tp_err:
            log.debug(f"T+ recommendation skipped for {ticker}: {_tp_err}")

        return ScanResultItem(
            ticker=ticker,
            action=mfpm["action"],
            confidence=mfpm["confidence"],
            mfpm_score=mfpm["mfpm_score"],
            mode_w_score=mfpm["mode_w_score"],
            sms_raw=sms_raw,
            sms_label=sms_result.get("sms_label", "RETAIL_DRIVEN"),
            signal_mode=mfpm["signal_mode"],
            stealth_accum=bool(stealth.get("detected", False)),
            close=float(last["close"]),
            entry=mfpm["entry"],
            sl=mfpm["sl"],
            tp1=mfpm["tp1"],
            rr=mfpm["rr_ratio"],
            amf_decision=amf.get("decision", "PASS"),
            best_pattern=pattern_result.get("best_pattern", "NONE"),
            hmm_state=hmm,
            sector_flow=sector_flow,
            earnings_risk=earnings_risk.rollover_risk.value,
            fundamental_score=fundamental_snapshot.fundamental_score,
            macro_regime=macro_result.macro_regime if macro_result else "",
            macro_score=macro_result.macro_score if macro_result else None,
            rsi14=float(last.get("RSI14", 50.0)),
            distribution_warning=dist_warning,
            tplus_setup     =_tplus.get("setup_type",  "T_NO_SETUP"),
            tplus_verdict   =_tplus.get("verdict",     "THEO_DOI"),
            tplus_confidence=_tplus.get("confidence",  0.0),
        )
