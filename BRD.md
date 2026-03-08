
# Business Requirement Document (BRD) for vnstock Applications

## 1. Introduction

This document outlines the business requirements for the "vnstock" suite of applications, which currently consists of two main components:

1.  **Captain Seventh QUANT TERMINAL (quant_app_v13.py):** A Python-based Streamlit application for in-depth quantitative analysis of the Vietnam stock market.
2.  **VN Stock Terminal (vn-stock-realtime.jsx):** A React-based web application for real-time monitoring of the Vietnam stock market.

The purpose of this document is to define the scope, features, and functional and non-functional requirements for these applications to ensure they meet the business objectives and user needs.

## 2. Business Objectives

*   To provide a comprehensive and reliable platform for analyzing and monitoring the Vietnam stock market.
*   To empower users with data-driven insights for making informed investment decisions.
*   To offer both real-time monitoring and in-depth historical analysis capabilities.
*   To ensure the accuracy and timeliness of the financial data presented to the users.
*   To provide a user-friendly and intuitive interface for both technical and non-technical users.

## 3. Scope

The scope of this project covers the analysis, maintenance, and enhancement of the two existing applications.

**In Scope:**

*   Analysis of the existing codebase to identify errors, limitations, and areas for improvement.
*   Bug fixing and performance optimization.
*   Enhancement of existing features.
*   Addition of new features to adapt to the specific needs of the Vietnam stock market.
*   Improvement of the data pipeline to ensure data quality and reliability.
*   UI/UX improvements for better usability.

**Out of Scope:**

*   Development of a mobile application (unless specified as a future enhancement).
*   Integration with brokerage accounts for direct trading.
*   Providing personalized investment advice.

## 4. Functional Requirements

### 4.1. Captain Seventh QUANT TERMINAL (quant_app_v13.py)

| Feature ID | Feature Name | Description |
| :--- | :--- | :--- |
| F-QT-001 | Data Pipeline | The application must fetch historical and fundamental data from multiple reliable sources (DNSE, SSI, CafeF, VNDirect FINFO) for stocks listed on HOSE, HNX, and UPCOM. |
| F-QT-002 | Technical Analysis | The application must calculate and display a comprehensive set of technical indicators, including but not limited to: SMA, RSI, Bollinger Bands, MACD, Stochastic, ATR, OBV, ADX, Williams %R, and CCI. |
| F-QT-003 | Fundamental Analysis | The application must display company profiles, financial statements (income, balance sheet, cash flow), key financial ratios, news, and dividend history. |
| F-QT-004 | Market Scanner | The application must provide a market scanner to screen stocks based on user-defined criteria (e.g., trend, liquidity, RSI). |
| F-QT-005 | Buy/Sell Signals | The application must generate buy/sell signals based on a composite scoring system that combines multiple technical indicators. |
| F-QT-006 | Deep Audit | The application must provide a "Deep Audit" feature for in-depth analysis of a single stock, including technical charts, fundamental data, and "doi lai" detection. |
| F-QT-007 | Backtesting | The application must include a T+2 backtesting module to simulate trading strategies and evaluate their performance. |
| F-QT-008 | ML Forecasting | The application must provide price forecasting using machine learning models (Prophet, ARIMA, and a scikit-learn ensemble). |
| F-QT-009 | Global Markets | The application must display data for global market indicators and their potential impact on the Vietnam market. |
| F-QT-010 | Bilingual Support | The application must support both Vietnamese and English languages. |

### 4.2. VN Stock Terminal (vn-stock-realtime.jsx)

| Feature ID | Feature Name | Description |
| :--- | :--- | :--- |
| F-ST-001 | Real-time Data | The application must fetch and display real-time stock data from the TradingView scanner API. |
| F-ST-002 | Watchlist | The application must allow users to create and manage a watchlist of stocks. |
| F-ST-003 | Real-time Monitoring | The application must display real-time price information, including change, percentage change, and price levels (ceiling, floor, reference). |
| F-ST-004 | Technical Indicators | The application must display real-time values for key technical indicators like RSI, SMA20, and SMA50. |
| F-ST-005 | Buy/Sell Signals | The application must provide real-time buy/sell signals based on TradingView's recommendations. |
| F-ST-006 | Interactive UI | The application must provide an interactive and user-friendly interface with features like price bars, RSI bars, and a detail modal for each stock. |
| F-ST-007 | Auto-refresh | The application must automatically refresh the data at a regular interval (e.g., every 30 seconds). |

## 5. Non-Functional Requirements

| Requirement ID | Category | Requirement |
| :--- | :--- | :--- |
| NF-001 | Performance | The applications must be responsive and load data within a reasonable time frame. API calls should have appropriate timeouts. |
| NF-002 | Reliability | The applications must be stable and available during market hours. The data pipeline should be robust to handle API failures and data inconsistencies. |
| NF-003 | Usability | The user interfaces should be intuitive, easy to navigate, and visually appealing. |
| NF-004 | Scalability | The applications should be able to handle a growing number of users and a larger watchlist without significant performance degradation. |
| NF-005 | Security | The applications should not expose any sensitive user data. All communication with external APIs should be secure. |
| NF-006 | Maintainability | The code should be well-structured, documented, and easy to maintain and extend. |
| NF-007 | Compatibility | The web application should be compatible with modern web browsers (Chrome, Firefox, Safari, Edge). |

## 6. Assumptions and Dependencies

*   The availability and reliability of the external APIs (DNSE, SSI, CafeF, VNDirect FINFO, TradingView) are critical for the functioning of the applications.
*   The user has a stable internet connection to use the applications.
*   The user has the necessary software (e.g., Python, Streamlit, Node.js) installed to run the applications locally.
