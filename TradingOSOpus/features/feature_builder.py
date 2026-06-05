"""features/feature_builder.py – Build ML feature matrix."""
import pandas as pd, numpy as np
from features.technical import build_all_indicators

class FeatureBuilder:
    def __init__(self):
        self._feature_cols = []

    def build(self, df, horizon=5):
        featured = build_all_indicators(df)
        featured["target"] = (featured["close"].shift(-horizon) > featured["close"]).astype(int)
        featured["target_return"] = featured["close"].pct_change(horizon).shift(-horizon)
        return featured

    def get_feature_columns(self, df):
        exclude = {"date", "target", "target_return", "open", "high", "low", "close", "volume"}
        self._feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ["float64", "int64"]]
        return self._feature_cols

    def prepare_ml_data(self, df, test_ratio=0.2):
        feat_cols = self.get_feature_columns(df)
        clean = df.dropna(subset=feat_cols + ["target"]).copy()
        X = clean[feat_cols].values; y = clean["target"].values
        split = int(len(X) * (1 - test_ratio))
        return X[:split], X[split:], y[:split], y[split:], feat_cols