TECHNICAL PROPOSAL: CANSLIM QUANT & MARKET MANIPULATION DETECTION SYSTEM

The Academic Board proposes a complete technical framework for a CANSLIM-based trading system, optimized for the Vietnamese market (100 tickers, including Small and Mid-caps). The system features advanced breakout detection, fundamental integration, and "Pump and Dump" early warning signals.1. Fundamental Data Architecture (EPS & Financial Reports)To satisfy the C and A criteria of CANSLIM, the system integrates with VNSTOCK API to fetch data from SSI and TCBS.Criteria: Focus on companies with EPS growth $> 25\%$ and ROE $> 17\%$.Python# Python Implementation for EPS Growth Filtering

# Derived from
def filter_canslim_stocks(df):
    eligible = df[(df['eps_growth'] >= 0.25) & (df['roe'] >= 0.17)]
    return eligible

2. Base Breakout & Momentum EngineThe system scans for classic William O'Neil bases: Cup with Handle and Flat Bases.Rule: Buying occurs only when the price crosses the "Pivot Point" on volume that is at least $1.4\times$ to $2\times$ the 50-day average.Python# Breakout Detection Logic

def get_pivot_breakout(df):
    pivot = df['high'].iloc[-20:-1].max()
    is_breakout = (df['close'].iloc[-1] > pivot) & \
                  (df['volume'].iloc[-1] > df['volume'].rolling(50).mean().iloc[-1] * 1.5)
    return is_breakout

3. Manipulation & False Breakout Detection (Risk Management)To protect investors in the Small/Mid-cap space, the system employs Anomaly Detection to flag "Pump and Dump" schemes and "Fakeouts."Pump Detection: High Volume Z-score ($> 3$) combined with extreme price jumps without fundamental catalysts.False Breakout: A breakout on low volume ($< 30\%$ below average) or a rapid price reversal back into the base within 48 hours.Python# Anomaly Scoring for Pump and Dump detection

def get_manipulation_score(df):
    vol_spike = df['volume'] / df['volume'].rolling(20).mean()
    price_change = df['close'].pct_change()
    # High score indicates high probability of manipulation
    manip_score = (vol_spike * 0.5) + (price_change * 2.0)
    return manip_score

4. Recommendation & Trading StrategyThe system classifies tickers into an Investment Matrix:True CANSLIM Leaders: High RS Rating ($> 80$) + Base Breakout + Institutional Support (I).Momentum Swing: Riding the "Pump" phase using tight trailing stops, while exiting immediately if the Anomaly Score signals a "Dump" is imminent.Hội đồng khẳng định rằng việc kết hợp dữ liệu tài chính (Fundamentals) và phân tích hành vi dòng tiền (VSA) là phương pháp duy nhất để tối đa hóa lợi nhuận và phòng tránh các bẫy thao túng tại thị trường chứng khoán Việt Nam.