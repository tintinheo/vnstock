"""models/ensemble.py – Multi-model weighted voting ensemble."""
import numpy as np

class EnsemblePredictor:
    def __init__(self, models=None, weights=None):
        self.models = models or []; self.weights = weights

    def add_model(self, model, weight=1.0):
        self.models.append(model)
        if self.weights is None: self.weights = []
        self.weights.append(weight)

    def predict(self, X):
        if not self.models: return np.zeros(len(X))
        w = np.array(self.weights if self.weights else [1.0] * len(self.models))
        w = w / w.sum()
        preds = np.zeros(len(X))
        for model, weight in zip(self.models, w):
            try:
                p = model.predict(X)
                if len(p) == len(X): preds += weight * p
            except Exception: pass
        return (preds > 0.5).astype(int)