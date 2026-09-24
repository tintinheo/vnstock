"""models/linear_model.py – Linear + Lasso regression."""
import numpy as np
from sklearn.linear_model import LinearRegression, Lasso
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

class LinearPredictor:
    def __init__(self, method="lasso", alpha=0.01):
        self.model = Lasso(alpha=alpha) if method == "lasso" else LinearRegression()

    def train(self, X, y): self.model.fit(X, y); return self
    def predict(self, X): return self.model.predict(X)

    def evaluate(self, X, y):
        preds = self.predict(X)
        return {"mse": mean_squared_error(y, preds), "mae": mean_absolute_error(y, preds),
                "r2": r2_score(y, preds), "mape": np.mean(np.abs((y - preds) / (y + 1e-10))) * 100}