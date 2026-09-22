TECHNICAL PROPOSAL: MULTI-TIMEFRAME FORECASTING SYSTEM (MTF-FORECAST)As the Academic Board, we propose a technical solution that transforms raw SSI data into actionable candlestick insights for F0 investors.1. The Core MethodologyThe system employs Recursive Multi-Step Forecasting. By inputting $N$ (number of days), the AI agent utilizes the VN-4 Factor Model to rank tickers and then projects the future OHLC values using a Stacked BiGRU architecture optimized by Particle Swarm Optimization (PSO).2. Implementation Logic (Python Snippets)A. Forecasting Confidence Interval (Geometric Brownian Motion)Used to establish the "High/Low" wick boundaries with 95% confidence.Pythonimport numpy as np

def forecast_with_confidence(s0, mu, sigma, t=1):
    """
    GBM Formula for price projection
   
    """
    # Expected Price E(St) = S0 * exp(mu * t)
    expected_price = s0 * np.exp(mu * t)
    # Confidence Interval [lower, upper]
    lower = np.exp(np.log(s0) + (mu - 0.5 * sigma**2) * t - 1.96 * sigma * np.sqrt(t))
    upper = np.exp(np.log(s0) + (mu - 0.5 * sigma**2) * t + 1.96 * sigma * np.sqrt(t))
    return expected_price, lower, upper
B. Position Sizing (Half-Kelly for F0s)Calculates the exact number of shares based on the probability of a "Catastrophic Loss" (similar to the DHC chart scenario).Pythondef calculate_f0_position(p_win, b_ratio, r_catas, lambd_loss):
    """
    p_win: Win rate, r_catas: Probability of crash, lambd_loss: Crash size
    [5]
    """
    expectation = (b_ratio * p_win) - (1 - p_win - r_catas) - (lambd_loss * r_catas)
    f_star = expectation / b_ratio
    # Apply Half-Kelly (0.5 fraction) for 20M VND bankroll safety
    return max(0, f_star * 0.5)
    
3. Final Output LogicThe system visualizes the Predicted Candle by mapping the BiGRU outputs to a graphic template.Case C47 Logic: If $Low_{pred} \ll Open_{pred} \approx Close_{pred}$, the system triggers an "Accumulate" signal at the 13:00 T+2.5 window.Case DHC Logic: If $Open_{pred} = High_{pred}$ and $Close_{pred} = Low_{pred}$ with high Volume, the system triggers an "Absolute Avoidance" alert.Hội đồng khẳng định rằng việc kết hợp phân tích định lượng (Quantitative) và nhận diện mẫu hình (Pattern Recognition) là cách duy nhất để nhà đầu tư F0 đạt được độ chính xác tuyệt đối và loại bỏ sai lệch tâm lý trong mọi khung thời gian giao dịch.