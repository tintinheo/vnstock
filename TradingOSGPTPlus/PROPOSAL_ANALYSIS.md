# Proposal Analysis

## Implementation Slice

The proposal describes a full production trading decision-support operating system. This repository implements the Phase 1 MVP slice:

- Public-first OHLCV fetch pipeline with KBS before CafeF.
- Explicit backup placeholders for Vietstock, FireAnt, and DNSE until endpoint contracts and terms are validated.
- No `vnstock` dependency.
- No fake/random market-data fallback.
- Valid cache fallback only after live source failure.
- HTTP 503 when real sources and valid cache fail.
- FastAPI decision API.
- Streamlit local UI.
- JSONL audit logging.
- Indicator, regime, five-horizon strategy, risk sizing, and simple backtest modules.

## Highest-Risk Areas From The Proposal

1. Data-source drift: KBS and CafeF are public/undocumented enough that layouts and payloads can change.
2. Price unit mismatch: CafeF is normalized as thousands-to-VND; KBS historical data is treated as actual VND.
3. Liquidity and daily-limit execution: the MVP warns but does not fully event-model limit-lock non-fills.
4. Backtest optimism: costs and slippage are included, but settlement and daily-limit queue priority need a deeper event engine.
5. ML claims: ML is deliberately disabled in MVP until walk-forward validation and model governance are built.

## Production Follow-Up

- Verify KBS payload schema against FPT, VCB, HPG, VCG, and UPCOM names.
- Add lawful and stable backup adapters after terms review.
- Replace seed universe with live universe reconstruction.
- Add Vietnam holiday calendar and corporate-action adjustment.
- Extend backtest engine with T+2.5 cash ledger, taxes, slippage by liquidity, and daily price-band non-fill logic.
- Add React scanner if Streamlit becomes too limited for batch workflows.

