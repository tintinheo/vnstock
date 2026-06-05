"""tests/test_models.py – Test ML/DL models."""
import numpy as np
from models.xgboost_model import XGBoostDirectional
from models.linear_model import LinearPredictor

def _data(n=500, nf=10):
    np.random.seed(42); X = np.random.randn(n,nf); y = (X[:,0]+X[:,1]*0.5>0).astype(int); return X,y

def test_xgboost_train_predict():
    X,y = _data(); m = XGBoostDirectional(); m.train(X[:400],y[:400])
    assert len(m.predict(X[400:])) == 100

def test_xgboost_walk_forward():
    X,y = _data(); m = XGBoostDirectional()
    wf = m.walk_forward_validate(X,y,n_splits=3)
    assert "overall_accuracy" in wf and len(wf["folds"]) == 3

def test_linear_predictor():
    np.random.seed(42); X = np.random.randn(200,5); y = X[:,0]*0.5+X[:,2]*0.3+np.random.randn(200)*0.1
    m = LinearPredictor("lasso"); m.train(X[:150],y[:150])
    assert m.evaluate(X[150:],y[150:])["r2"] > 0.5
