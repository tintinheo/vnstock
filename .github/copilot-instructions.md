# Workspace Instructions for the `vnstock` project

This document provides instructions for GitHub Copilot to effectively assist with the development of the `vnstock` project.

## About the Project

The `vnstock` project is a quantitative analysis and AI forecasting platform for the Vietnam stock market. It is built as a Python Streamlit application.

- **Main Application File**: `app/quant_app_v13.py`
- **Primary Framework**: Streamlit
- **Core Libraries**: `pandas`, `numpy`, `plotly`, `requests`, `yfinance`, `prophet`, `statsmodels`, `scikit-learn`.

## How to Run the Application

The application is a Streamlit app. To run it, navigate to the `app` directory and use the following command.

```bash
# From the c:\\Users\\TheCaptain7th\\OneDrive\\portfolio\\vnstock\\app directory
python -m streamlit run quant_app_v13.py
```

## Key Architectural Concepts

### Data Pipeline

The application uses a multi-source data pipeline to ensure reliability. The data sources are tried in the following order:
1.  **DNSE Entrade**: Primary, fast, and covers all exchanges.
2.  **SSI iBoard**: Secondary, stable, covers HOSE/HNX.
3.  **CafeF**: Fallback using HTML scraping and a JSON API.
4.  **yFinance**: Final fallback for global indices and as a last resort for VN tickers.

The main function for this is `download_data()` in `app/quant_app_v13.py`.

### UI Structure

The user interface is built with Streamlit and is organized into multiple tabs. Each tab's content is rendered by a dedicated function named `render_<tab_name>_tab()`. These are all called from the `main()` function.

### Core Features

- **Market Scanner**: Scans a watchlist of tickers for trading signals based on technical indicators.
- **Deep Audit**: Provides an in-depth analysis of a single ticker, including 9 technical indicators, fundamental data from VNDirect, and advanced analytics.
- **Backtesting**: A T+2 backtesting engine based on RSI, Bollinger Bands, and ATR stop-loss.
- **ML Forecasting**: An ensemble of 7 different models (from statistical models like ARIMA to ML models like RandomForest and Prophet) to forecast future prices.
- **Global Markets**: Monitors global indices and commodities and analyzes their impact on the Vietnam market.

## Development Guidelines

- When adding new features, follow the existing modular structure. For a new tab, create a new `render_<new_tab_name>_tab()` function.
- Ensure any new data fetching logic is integrated into the `download_data` pipeline if it's a primary data source.
- All user-facing text should be added to both the `_LANG_VI` and `_LANG_EN` dictionaries to support bilingual capabilities.
- When modifying data fetching or processing, use the "System Smoke Test" tab to validate that all data sources and functions are working correctly.
- Log all errors and important events to `data/error_log.txt` using the `_log` object.
- The user prefers using the `vnstock` package for market data, not `vnstock3`.
