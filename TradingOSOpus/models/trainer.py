"""models/trainer.py – Full training pipeline orchestrating all models."""
from data.data_manager import DataManager
from features.feature_builder import FeatureBuilder
from models.xgboost_model import XGBoostDirectional
from models.linear_model import LinearPredictor
from config.settings import HORIZONS

class ModelTrainer:
    def __init__(self):
        self.dm = DataManager(); self.fb = FeatureBuilder()

    def train_single(self, ticker, horizon_key="1W", start="2016-01-01"):
        days = HORIZONS.get(horizon_key, {}).get("days", 5)
        df = self.dm.get_ohlcv(ticker, start=start)
        if df.empty or len(df) < 200: return {"error": f"Insufficient data for {ticker}"}
        featured = self.fb.build(df, horizon=days)
        X_train, X_test, y_train, y_test, feat_cols = self.fb.prepare_ml_data(featured)
        if len(X_train) < 50: return {"error": "Not enough training samples"}
        xgb = XGBoostDirectional(); xgb.train(X_train, y_train, feature_names=feat_cols)
        xgb_metrics = xgb.evaluate(X_test, y_test)
        wf = xgb.walk_forward_validate(
            featured.dropna(subset=feat_cols + ["target"])[feat_cols].values,
            featured.dropna(subset=feat_cols + ["target"])["target"].values, n_splits=3)
        xgb.save(f"xgb_{ticker}_{horizon_key}")
        lasso = LinearPredictor("lasso"); lasso.train(X_train, y_train)
        lasso_metrics = lasso.evaluate(X_test, y_test)
        return {"ticker": ticker, "horizon": horizon_key, "samples": len(X_train) + len(X_test),
                "xgboost": xgb_metrics, "walk_forward": wf, "lasso": lasso_metrics}

    def train_all(self, ticker, start="2016-01-01"):
        return {h: self.train_single(ticker, h, start) for h in HORIZONS}