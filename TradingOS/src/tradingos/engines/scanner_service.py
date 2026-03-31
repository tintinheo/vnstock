"""Scanner Service — 7-stage universe scanner pipeline (SRS §3.3)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_universe
from ..data.cache import cache
from ..data.schemas import ScanResult, ScanResultItem, ScanRequest
from ..core import (
    compute_indicators,
    run_amf,
    detect_amd_phase,
    compute_smart_money_score,
    detect_stealth_accumulation,
    detect_patterns,
    detect_hmm_state,
    compute_mfpm,
)
from ..core.money_flow import proxy_whale_net_from_daily, compute_multiday_whale_flow
from ..utils.logging import get_logger
from ..utils.config import cfg

log = get_logger("scanner_service")


class ScannerService:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def scan(self, request: ScanRequest) -> ScanResult:
        """
        Full 7-stage scanner pipeline.

        Stage 1: Universe selection
        Stage 2: OHLCV fetch
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
            # Full universe: HOSE + HNX
            max_scan = int(cfg.strategy("universe", "max_universe_size", default=150))
            hose = fetch_universe("HOSE")
            hnx  = fetch_universe("HNX")
            # fetch_universe returns list[str]; dedupe preserving order
            tickers = list(dict.fromkeys(hose + hnx))
            tickers = tickers[:max_scan]

        log.info(f"Stage 1 done: {len(tickers)} tickers")

        # ── Stages 2–6: Parallel ─────────────────────────────────────────
        items: list[ScanResultItem] = []
        _ticker_timeout = int(cfg.strategy("scanner", "per_ticker_timeout_s", default=30))
        with ThreadPoolExecutor(max_workers=self.max_workers) as exc:
            futures = {exc.submit(self._score_ticker, t, request): t for t in tickers}
            for fut in as_completed(futures, timeout=None):
                ticker = futures[fut]
                try:
                    item = fut.result(timeout=_ticker_timeout)
                    if item is not None:
                        items.append(item)
                except TimeoutError:
                    log.warning(f"Scanner timeout ({_ticker_timeout}s) — skipping {ticker}")
                except Exception as e:
                    log.warning(f"Scanner skip {ticker}: {e}")

        # ── Stage 7: Sort ─────────────────────────────────────────────────
        items.sort(key=lambda x: x.mfpm_score, reverse=True)

        log.info(f"Scanner done: {len(items)} results")

        cache.put_audit({
            "event_type": "SCAN",
            "ticker": "BATCH",
            "action": f"{len(items)} results",
            "mfpm_score": 0,
            "sms_raw": 0,
            "confidence": "—",
        })

        return ScanResult(
            tickers_scanned=len(tickers),
            tickers_passed=len(items),
            results=items[:request.limit or 50],
            scan_ts=pd.Timestamp.now().isoformat(),
        )

    def _score_ticker(self, ticker: str, request: ScanRequest) -> ScanResultItem | None:
        """Score a single ticker through all stages. Returns None to skip."""
        df = fetch_ohlcv(ticker, days=120)
        if df.empty or len(df) < 40:
            return None

        df = compute_indicators(df)

        # Stage 4: AMF
        amf = run_amf(df, order_book=None)

        # Stage 5: SMS
        amd = detect_amd_phase(df)
        flow_df = proxy_whale_net_from_daily(df)
        mcvd = compute_multiday_whale_flow(flow_df)
        sms_result = compute_smart_money_score(ticker, df, flow_df, None, None, amd)
        sms_raw = sms_result.get("sms", 0)

        # Stage 6: MFPM
        pattern_result = detect_patterns(df)
        hmm = detect_hmm_state(df)
        mfpm = compute_mfpm(
            df=df,
            sms_result={**sms_result,
                        "stealth_detail": {},
                        "distribution_warning": "NONE",
                        "mcvd_detail": {**mcvd, "data_source": "PROXY_OHLCV"}},
            amf_result=amf,
            pattern_result=pattern_result,
            hmm_state=hmm,
            amd_phase=amd,
            horizons=[5],
        )

        last = df.iloc[-1]
        stealth = detect_stealth_accumulation(df, flow_df)
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
        )
