2. Strategic Assessment & Evaluation
T+2.5 Liquidity Dynamics: The verification confirms a massive surge in intraday liquidity after 13:00. For TCH and CII, the T+2.5 asset release was met with aggressive "bottom-fishing" demand, effectively turning a potential supply shock into a price catalyst.

VN-4 Model Validation: The Turnover and Size factors were dominant. These mid-cap stocks significantly outperformed the VN30 (+2.88%), validating our strategy that alpha is concentrated in high-turnover, smaller-cap names during volatility regimes.

Technical Pattern: The "Big White Candle" pattern observed across these tickers (S_S36) would have been flagged by a PSO-optimized MACD as a high-conviction buy signal.

3. Proposed Improvements for Absolute Precision
Based on the extreme volatility observed from March 9th to 11th, we propose adding these filters to the PSO algorithm:

Herding Deviation (CSAD): Measures market irrationality. If CSAD is low during a price spike, it indicates pure herding (dangerous for F0s); if high, it indicates fundamental-driven divergence.

Rolling Dynamic Beta: Implementing a 5-day rolling Beta to adjust position sizes (Kelly) dynamically as the market switches from "crash" to "recovery" mode within the T+2.5 window.

4. Implementation Formulas & Code
A. Cross-Sectional Absolute Deviation (CSAD) for Herding Detection
Used to prevent the algorithm from buying into irrational retail bubbles.

Python
def calculate_csad(stock_returns):
    """
    stock_returns: Array of returns for the portfolio (GEG, TCH, CII, VGC)
    
    """
    import numpy as np
    avg_return = np.mean(stock_returns)
    # CSAD = (1/N) * sum(|R_i,t - R_m,t|)
    csad = np.mean(np.abs(stock_returns - avg_return))
    return csad
B. Dynamic Position Sizing Adjustment (Fractional Kelly)
Calculates the adjusted capital allocation based on the previous session's volatility.

Python
def calculate_fractional_kelly(win_prob, gain_loss_ratio, market_volatility):
    """
    Adjusts f* based on current market stress (Catastrophic Risk filter)
    
    """
    # Standard Kelly: f = (bp - q) / b
    b = gain_loss_ratio
    p = win_prob
    q = 1 - p
    f_star = (b * p - q) / b
    
    # Apply Volatility Scaling (Half-Kelly or Quarter-Kelly)
    if market_volatility > 0.03: # Example: High stress threshold
        return max(0, f_star * 0.25) # Quarter Kelly
    return max(0, f_star * 0.5) # Half Kelly
The Academic Board confirms that the data from March 11, 2026, strongly supports our automated approach, with the added necessity of the "Herding Filter" to protect F0 investors from extreme sentiment shifts.