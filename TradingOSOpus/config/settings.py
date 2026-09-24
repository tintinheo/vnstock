"""config/settings.py – Central configuration."""
import os

TCBS_BASE = "https://apipubaws.tcbs.com.vn"
TCBS_BARS = f"{TCBS_BASE}/stock-insight/v2/stock/bars-long-term"
TCBS_TICKER = f"{TCBS_BASE}/stock-insight/v1/stock/overview"
TCBS_INTRADAY = f"{TCBS_BASE}/stock-insight/v1/intraday"
TCBS_LISTING = f"{TCBS_BASE}/stock-insight/v1/stock/listing"

VCI_BASE = "https://trading.vietcap.com.vn/api"
VCI_OHLC = f"{VCI_BASE}/chart/OHLCChart/gap-chart"
VCI_PRICE_BOARD = f"{VCI_BASE}/price/symbols/getList"
VCI_GRAPHQL = "https://trading.vietcap.com.vn/data-mt/graphql"
CAFEF_NEWS_URL = "https://cafef.vn/timeline/31/trang-{page}.chn"

DEFAULT_TICKERS = ["VNM","FPT","VCB","HPG","MBB","TCB","VHM","VIC","MSN","ACB",
    "STB","SSI","MWG","PNJ","REE","GVR","VRE","TPB","CTG","BID",
    "SAB","PLX","GAS","POW","VJC","HDB","SHB","EIB","KDH","DGC"]
VN30_TICKERS = ["ACB","BCM","BID","BVH","CTG","FPT","GAS","GVR","HDB","HPG",
    "MBB","MSN","MWG","PLX","POW","SAB","SHB","SSB","SSI","STB",
    "TCB","TPB","VCB","VHM","VIB","VIC","VJC","VNM","VPB","VRE"]

TRADING = {"initial_capital": 500_000_000, "commission_rate": 0.0015, "tax_rate": 0.001,
    "slippage_bps": 5, "max_position_pct": 0.20, "max_sector_pct": 0.35}
HORIZONS = {
    "1W": {"days": 5, "label": "Weekly Momentum"},
    "2W": {"days": 10, "label": "Swing Trading"},
    "1M": {"days": 22, "label": "Position Trading"},
    "3M": {"days": 66, "label": "Cycle Trading"},
    "5M": {"days": 110, "label": "Value Investing"},
}
LSTM_PARAMS = {"input_size": 16, "hidden_size": 64, "num_layers": 2, "dropout": 0.2,
    "seq_len": 30, "batch_size": 32, "epochs": 50, "lr": 0.001}
XGB_PARAMS = {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05, "subsample": 0.8,
    "colsample_bytree": 0.8, "objective": "binary:logistic", "eval_metric": "logloss",
    "use_label_encoder": False, "random_state": 42}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data_store")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "saved_models")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")