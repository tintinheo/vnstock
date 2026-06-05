"""models/xgboost_model.py – XGBoost directional classifier with walk-forward."""
import numpy as np, os, pickle
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from config.settings import XGB_PARAMS, MODEL_DIR

class XGBoostDirectional:
    def __init__(self, **kwargs):
        params = {**XGB_PARAMS, **kwargs}
        self.model = XGBClassifier(**params)
        self._feature_names = None

    def train(self, X, y, feature_names=None):
        self._feature_names = feature_names
        self.model.fit(X, y)
        return self

    def predict(self, X): return self.model.predict(X)
    def predict_proba(self, X): return self.model.predict_proba(X)

    def evaluate(self, X, y):
        preds = self.predict(X)
        return {"accuracy": accuracy_score(y, preds), "precision": precision_score(y, preds, zero_division=0),
                "recall": recall_score(y, preds, zero_division=0), "f1": f1_score(y, preds, zero_division=0)}

    def feature_importance(self, top_n=10):
        imp = self.model.feature_importances_
        names = self._feature_names or [f"f_{i}" for i in range(len(imp))]
        pairs = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)
        return pairs[:top_n]

    def walk_forward_validate(self, X, y, n_splits=5):
        fold_size = len(X) // (n_splits + 1); results = []
        for i in range(n_splits):
            train_end = fold_size * (i + 2); test_end = min(train_end + fold_size, len(X))
            if test_end <= train_end: break
            self.train(X[:train_end], y[:train_end])
            metrics = self.evaluate(X[train_end:test_end], y[train_end:test_end])
            results.append({"fold": i + 1, "train_size": train_end,
                            "test_size": test_end - train_end, **metrics})
        avg_acc = np.mean([r["accuracy"] for r in results]) if results else 0
        return {"folds": results, "overall_accuracy": round(avg_acc, 4)}

    def save(self, name="xgb_model"):
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "wb") as f: pickle.dump(self.model, f)
        return path

    def load(self, name="xgb_model"):
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "rb") as f: self.model = pickle.load(f)
        return self