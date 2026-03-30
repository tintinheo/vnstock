# tradingos

Vietnamese stock market automated trading operating system.

## Project Structure

```
tradingos/
├── src/tradingos/         # Main package
│   ├── core/               # Domain logic: signals, strategy, risk
│   ├── data/               # Data fetching, caching, normalization
│   ├── engines/            # Analysis engines (TA, ML, microstructure)
│   ├── ui/                 # Streamlit UI components / pages
│   └── utils/              # Shared utilities: logging, datetime, math
├── tests/
│   ├── unit/               # Pure unit tests (no network/DB)
│   └── integration/        # Tests requiring live APIs or DB
├── docs/                   # Architecture decisions, API specs
├── scripts/                # CLI tools, data backfill, maintenance
├── config/                 # YAML/TOML environment configs
└── .github/workflows/      # CI pipelines
```

## Quick Start

```bash
pip install -e ".[dev]"
streamlit run src/tradingos/ui/app.py
```

## Running Tests

```bash
python -m pytest tests/unit
```
