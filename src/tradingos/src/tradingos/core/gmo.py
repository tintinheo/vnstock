import numpy as np
import pandas as pd
from hmmlearn import hmm

def fit_hmm(features: np.ndarray) -> hmm.GaussianHMM:
    """
    Fits GaussianHMM with state-pinning to prevent label switching.
    features: array of [daily_return, realized_volatility_10d]
    """
    model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=300, random_state=42)
    model.fit(features)

    # Pin state order: sort by emission mean return (feature[0])
    order = np.argsort(model.means_[:, 0])
    
    model.means_ = model.means_[order]
    if model.covars_.ndim == 3:
        model.covars_ = model.covars_[order]
    else:
        model.covars_ = model.covars_[order]
        
    model.transmat_ = model.transmat_[order][:, order]
    model.startprob_ = model.startprob_[order]
    
    return model

def monthly_refit_hmm(full_history: np.ndarray, window_years: int = 3) -> hmm.GaussianHMM:
    """Refits the model on a rolling 3-year window to prevent regime drift."""
    trading_days = 252 * window_years
    if len(full_history) < trading_days:
        window_data = full_history # Fallback if history is too short
    else:
        window_data = full_history[-trading_days:]
    return fit_hmm(window_data)

def calibrate_herding_threshold(historical_variances: list, percentile: float = 10) -> float:
    """Returns the herding threshold based on historical cross-sectional variance."""
    if not historical_variances:
        return 0.0002 # Empirical VN estimate fallback
    return float(np.percentile(historical_variances, percentile))

def calculate_gmo_omega(sp500_above_sma: bool, dxy_falling: bool, oil_stable: bool, sbv_rate: float, vni_above_sma: bool) -> float:
    """
    Calculates the Macro Omega Score.
    Weights: S&P500(0.30), DXY(0.20), Oil(0.15), SBV(0.20), VNI(0.15)
    """
    omega = 0.0
    omega += 0.30 if sp500_above_sma else -0.30
    omega += 0.20 if dxy_falling else -0.20
    omega += 0.15 if oil_stable else -0.15
    omega += 0.20 if sbv_rate <= 4.5 else -0.20
    omega += 0.15 if vni_above_sma else -0.15
    return omega