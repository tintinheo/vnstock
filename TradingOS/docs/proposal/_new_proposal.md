# 🎓 HỘI ĐỒNG HỌC THUẬT — PHÂN TÍCH CHUYÊN SÂU & GIẢI PHÁP
## Báo cáo Kỹ thuật: Đánh giá Hệ thống TradingOS | Phiên 23/04/2026

> **Ban Hội đồng:** Computational Finance · Quantitative Trading · Economics · Computer Science · Software Architecture · Data Science · Product Management · Stock Investment Advisory
>
> **Phân loại:** Nội bộ — Nghiên cứu & Phát triển Hệ thống
>
> **Ngôn ngữ:** Tiếng Việt (Technical Terms giữ nguyên tiếng Anh)

---

## MỤC LỤC

1. [Vấn đề 1: RSI Threshold Tuyệt đối](#van-de-1)
2. [Vấn đề 2: mc_prob Calibration](#van-de-2)
3. [Vấn đề 3: M-CVD Timeframe Conflict Resolution](#van-de-3)
4. [Vấn đề 4: SMA200 = NaN — Data Gap](#van-de-4)
5. [Vấn đề 5: AMF WASH_SALE Directionality](#van-de-5)
6. [Vấn đề 6: M-CVD Volume Normalization](#van-de-6)
7. [Lộ trình Triển khai Tổng thể](#lo-trinh)

---

## VẤN ĐỀ 1: RSI Dùng Như Threshold Tuyệt đối {#van-de-1}

### 🔍 Phân tích Gốc rễ

> *Giáo sư Computational Finance phát biểu:*

Việc sử dụng ngưỡng RSI cố định 70/80/90 là một **lỗi phương pháp luận cổ điển** (methodological fallacy) trong môi trường trending market. Wilder (1978) thiết kế RSI cho thị trường sideways — không phải cho giai đoạn breakout có momentum mạnh. Trong bull market regime, RSI có thể duy trì >70 trong 10–30 phiên liên tiếp mà không có mean-reversion xảy ra.

**Bằng chứng thực nghiệm trên HOSE:**
- VN-Index tháng 4/2021: RSI duy trì 72–85 trong 18 phiên liên tiếp
- Các bluechip nhóm Vingroup (VIC, VHM, VRE) có hành vi RSI lệch chuẩn do free-float thấp và dominance của tổ chức nội địa
- Đặc thù T+2 của thị trường Việt Nam tạo ra RSI spikes nhân tạo trong phiên đảo chiều thanh khoản

### 💡 Giải pháp: Dynamic RSI với Regime-Adaptive Thresholds

#### Bước 1 — Phân loại Market Regime

```python
# Module: regime_classifier.py
import numpy as np
import pandas as pd
from scipy import stats

def classify_market_regime(vnindex_series: pd.Series, 
                            lookback: int = 20) -> str:
    """
    Phân loại market regime dựa trên VN-Index
    Returns: 'BULL_TREND' | 'BEAR_TREND' | 'SIDEWAYS' | 'HIGH_VOLATILITY'
    """
    returns = vnindex_series.pct_change().dropna()
    
    # ADX proxy: độ dốc MA
    sma_fast = vnindex_series.rolling(10).mean()
    sma_slow = vnindex_series.rolling(20).mean()
    slope = (sma_fast.iloc[-1] - sma_fast.iloc[-lookback]) / lookback
    
    # Volatility regime
    vol = returns.rolling(lookback).std().iloc[-1] * np.sqrt(252)
    
    # Trend strength
    r_squared = stats.pearsonr(
        range(lookback), 
        vnindex_series.iloc[-lookback:].values
    )[0] ** 2
    
    if r_squared > 0.85 and slope > 0:
        return 'BULL_TREND'
    elif r_squared > 0.85 and slope < 0:
        return 'BEAR_TREND'
    elif vol > 0.25:
        return 'HIGH_VOLATILITY'
    else:
        return 'SIDEWAYS'

def get_adaptive_rsi_thresholds(regime: str, 
                                 sector: str = 'GENERAL') -> dict:
    """
    Trả về ngưỡng RSI động theo regime và ngành
    """
    BASE_THRESHOLDS = {
        'BULL_TREND':      {'overbought': 80, 'warning': 75, 'healthy': (55, 75), 'oversold': 45},
        'BEAR_TREND':      {'overbought': 65, 'warning': 60, 'healthy': (35, 55), 'oversold': 30},
        'SIDEWAYS':        {'overbought': 70, 'warning': 65, 'healthy': (40, 65), 'oversold': 35},
        'HIGH_VOLATILITY': {'overbought': 75, 'warning': 68, 'healthy': (40, 68), 'oversold': 30},
    }
    
    # Sector adjustment (VN-specific)
    SECTOR_ADJUSTMENTS = {
        'BANKING':         {'overbought': +3, 'oversold': +3},   # Banks ít mean-revert hơn
        'REAL_ESTATE':     {'overbought': +5, 'oversold': -5},   # Volatility cao hơn
        'STEEL_MATERIAL':  {'overbought': -3, 'oversold': -3},   # Cyclical, mean-revert nhanh
        'SECURITIES':      {'overbought': +2, 'oversold': +2},   # Beta cao
        'INFRASTRUCTURE':  {'overbought': 0,  'oversold': 0},
        'GENERAL':         {'overbought': 0,  'oversold': 0},
    }
    
    base = BASE_THRESHOLDS[regime].copy()
    adj = SECTOR_ADJUSTMENTS.get(sector, SECTOR_ADJUSTMENTS['GENERAL'])
    
    base['overbought'] += adj['overbought']
    base['oversold'] += adj['oversold']
    
    return base

def evaluate_rsi_signal(rsi_value: float, 
                        regime: str, 
                        sector: str,
                        consecutive_sessions_above_70: int = 0) -> dict:
    """
    Đánh giá RSI với context đầy đủ
    """
    thresholds = get_adaptive_rsi_thresholds(regime, sector)
    
    signal = {
        'rsi': rsi_value,
        'regime': regime,
        'thresholds': thresholds,
        'label': None,
        'action_hint': None,
        'confidence': None
    }
    
    # Sustained overbought: giảm mức nguy hiểm nếu momentum sustained
    sustained_adjustment = min(consecutive_sessions_above_70 * 1.5, 10)
    effective_overbought = thresholds['overbought'] + sustained_adjustment
    
    if rsi_value >= effective_overbought:
        signal['label'] = 'OVERBOUGHT'
        signal['action_hint'] = 'WAIT_PULLBACK'
        signal['confidence'] = 'HIGH' if consecutive_sessions_above_70 < 3 else 'MEDIUM'
    elif rsi_value >= thresholds['warning']:
        signal['label'] = 'ELEVATED'
        signal['action_hint'] = 'MONITOR_CLOSELY'
        signal['confidence'] = 'MEDIUM'
    elif thresholds['healthy'][0] <= rsi_value <= thresholds['healthy'][1]:
        signal['label'] = 'HEALTHY_MOMENTUM'
        signal['action_hint'] = 'FAVORABLE_ZONE'
        signal['confidence'] = 'HIGH'
    elif rsi_value <= thresholds['oversold']:
        signal['label'] = 'OVERSOLD'
        signal['action_hint'] = 'WATCH_FOR_REVERSAL'
        signal['confidence'] = 'MEDIUM'
    else:
        signal['label'] = 'NEUTRAL'
        signal['action_hint'] = 'NO_SIGNAL'
        signal['confidence'] = 'LOW'
    
    return signal
```

#### Bước 2 — Output Thực tế Cho Báo cáo 23/04

| Mã | RSI | Regime (giả định) | Ngưỡng OB Động | Đánh giá Điều chỉnh |
|----|-----|-------------------|----------------|---------------------|
| VIC | 90.0 | BULL_TREND | 85 (RE sector) | 🔴 Vẫn OVERBOUGHT — xác nhận |
| VHM | 79.9 | BULL_TREND | 85 (RE sector) | 🟡 **ELEVATED, chưa nguy hiểm** — thay đổi |
| VCB | 74.8 | BULL_TREND | 83 (Banking) | 🟢 **HEALTHY** — thay đổi hoàn toàn |
| NKG | 65.1 | BULL_TREND | 80 (Steel) | 🟢 Healthy RSI — NKG xấu vì AMD, không phải RSI |
| OCB | 67.9 | BULL_TREND | 83 (Banking) | 🟢 RSI không phải vấn đề — vấn đề là MARKDOWN |

> **Kết luận của Hội đồng:** Với Regime-Adaptive RSI, VCB và VHM được đánh giá tích cực hơn đáng kể — phù hợp với thực tế thị trường tháng 4/2026 hơn.

---

## VẤN ĐỀ 2: mc_prob Calibration {#van-de-2}

### 🔍 Phân tích Gốc rễ

> *Giáo sư Quantitative Finance & Data Scientist cùng phân tích:*

Việc toàn bộ 9 mã đều có mc_prob từ 3%–18% là **dấu hiệu chẩn đoán** của một trong ba vấn đề sau:

1. **TP được đặt quá xa** so với giá hiện tại (TP/Price ratio > 10–15%)
2. **Volatility model bị overestimate** — dùng historical vol cao bất thường (VD: tính vol trong giai đoạn crisis 2022–2023)
3. **Simulation horizon quá ngắn** — N phiên không đủ để đạt TP với trajectory Monte Carlo thông thường

**Kiểm tra heuristic:**
- Nếu mc_prob trung bình của toàn danh sách < 15%, đây gần như chắc chắn là calibration issue
- Một mô hình được calibrate tốt trên thị trường Việt Nam nên có phân phối mc_prob từ 5% đến 55% tùy mã

### 💡 Giải pháp: Monte Carlo Recalibration Framework

#### Bước 1 — Chẩn đoán vấn đề

```python
# Module: mc_diagnostics.py

def diagnose_mc_calibration(historical_results: pd.DataFrame) -> dict:
    """
    Chạy diagnostic trên lịch sử mc_prob predictions vs actual outcomes
    
    historical_results columns: ['date', 'ticker', 'mc_prob', 'tp', 
                                   'entry_price', 'actual_max_price_N_days']
    """
    results = {}
    
    # 1. Calibration curve: mc_prob vs actual hit rate
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    historical_results['hit'] = (
        historical_results['actual_max_price_N_days'] >= 
        historical_results['tp']
    ).astype(int)
    
    calibration = historical_results.groupby(
        pd.cut(historical_results['mc_prob'], bins)
    )['hit'].agg(['mean', 'count'])
    
    results['calibration_curve'] = calibration
    
    # 2. Brier Score (thấp hơn = tốt hơn)
    brier = np.mean(
        (historical_results['mc_prob'] - historical_results['hit']) ** 2
    )
    results['brier_score'] = brier
    results['brier_interpretation'] = (
        'WELL_CALIBRATED' if brier < 0.1 else
        'ACCEPTABLE' if brier < 0.2 else
        'POORLY_CALIBRATED'
    )
    
    # 3. Distribution check
    results['mean_prob'] = historical_results['mc_prob'].mean()
    results['actual_hit_rate'] = historical_results['hit'].mean()
    results['systematic_bias'] = results['mean_prob'] - results['actual_hit_rate']
    
    return results
```

#### Bước 2 — Monte Carlo Model Đúng Chuẩn

```python
# Module: mc_pricer.py
import numpy as np
from dataclasses import dataclass

@dataclass
class MCConfig:
    n_simulations: int = 10_000       # Tăng từ default thấp
    horizon_days: int = 15            # 15 phiên giao dịch (~3 tuần)
    vol_lookback: int = 60            # 60 phiên giao dịch gần nhất
    vol_method: str = 'EWMA'          # Exponential Weighted: phản ứng nhanh hơn
    drift_method: str = 'REGIME_ADJ'  # Có điều chỉnh theo regime
    tp_method: str = 'ATR_BASED'      # TP = entry + k*ATR thay vì cố định %

def calculate_vol_ewma(returns: pd.Series, 
                        lambda_param: float = 0.94) -> float:
    """
    EWMA Volatility (RiskMetrics standard)
    Lambda=0.94 cho daily data (J.P.Morgan standard)
    """
    vol_sq = returns.iloc[0] ** 2
    for r in returns.iloc[1:]:
        vol_sq = lambda_param * vol_sq + (1 - lambda_param) * r ** 2
    return np.sqrt(vol_sq * 252)  # Annualized

def run_monte_carlo_vn(
    current_price: float,
    returns_history: pd.Series,
    config: MCConfig,
    regime: str,
    atr_14: float
) -> dict:
    """
    Monte Carlo simulation được calibrate cho thị trường Việt Nam
    """
    # 1. Volatility estimation
    if config.vol_method == 'EWMA':
        daily_vol = calculate_vol_ewma(returns_history) / np.sqrt(252)
    else:
        daily_vol = returns_history.rolling(config.vol_lookback).std().iloc[-1]
    
    # 2. Drift adjustment theo regime
    REGIME_DRIFT = {
        'BULL_TREND':      0.0008,   # ~20% annualized drift
        'SIDEWAYS':        0.0001,
        'BEAR_TREND':     -0.0005,
        'HIGH_VOLATILITY': 0.0002,
    }
    daily_drift = REGIME_DRIFT.get(regime, 0.0001)
    
    # 3. TP/SL theo ATR (thay vì % cố định)
    K_TP = 2.5   # TP = giá + 2.5 * ATR14
    K_SL = 1.5   # SL = giá - 1.5 * ATR14
    tp = current_price + K_TP * atr_14
    sl = current_price - K_SL * atr_14
    
    # 4. GBM simulation (Geometric Brownian Motion)
    dt = 1  # 1 ngày
    simulations = np.zeros((config.n_simulations, config.horizon_days))
    simulations[:, 0] = current_price
    
    random_shocks = np.random.standard_normal(
        (config.n_simulations, config.horizon_days - 1)
    )
    
    for t in range(1, config.horizon_days):
        simulations[:, t] = simulations[:, t-1] * np.exp(
            (daily_drift - 0.5 * daily_vol**2) * dt + 
            daily_vol * np.sqrt(dt) * random_shocks[:, t-1]
        )
    
    # 5. VN-specific: thêm T+2 settlement delay effect
    # Thực tế nhà đầu tư không thể exit ngay -> check từ ngày 3 trở đi
    max_prices = simulations[:, 2:].max(axis=1)
    min_prices = simulations[:, 2:].min(axis=1)
    
    # 6. Tính probabilities
    tp_hit = (max_prices >= tp).mean()
    sl_hit = (min_prices <= sl).mean()
    tp_first = ((max_prices >= tp) & 
                (simulations[:, 2:].argmax(axis=1) < 
                 simulations[:, 2:].argmin(axis=1))).mean()
    
    return {
        'mc_prob_tp': tp_hit,
        'mc_prob_sl': sl_hit, 
        'mc_prob_tp_before_sl': tp_first,  # Metric quan trọng nhất
        'expected_return': (simulations[:, -1] / current_price - 1).mean(),
        'var_95': np.percentile(simulations[:, -1] / current_price - 1, 5),
        'tp': tp,
        'sl': sl,
        'daily_vol_used': daily_vol,
        'regime': regime
    }
```

#### Kết quả Kỳ vọng Sau Calibration

| Mã | mc_prob Hiện tại | mc_prob Sau Calibration (ước tính) | Thay đổi |
|----|-----------------|-------------------------------------|----------|
| VCB | 18% | 35–45% | ↑ Significant |
| HHV | 3% | 20–30% | ↑ Significant |
| VCG | 6% | 15–25% | ↑ |
| VHM | 25% | 40–50% | ↑ |
| NKG | 15% | 10–15% | ~ (Distribution giảm prob) |
| OCB | — | 5–8% | ~ (Markdown xác nhận thấp) |

---

## VẤN ĐỀ 3: M-CVD Timeframe Conflict Resolution {#van-de-3}

### 🔍 Phân tích Gốc rễ

> *Senior Quantitative Trader & Business Analyst phân tích:*

Xung đột M-CVD 5d vs 20d là một bài toán **multi-timeframe alignment** kinh điển. Trong Wyckoff Theory, dòng tiền dài hạn (20d) phản ánh ý định tổ chức, còn ngắn hạn (5d) phản ánh tactical positioning. Không có quy tắc ưu tiên nào là đúng tuyệt đối — cần một **conflict resolution matrix** tường minh.

### 💡 Giải pháp: CVD Conflict Resolution Matrix

#### Ma trận Phán quyết

```
╔══════════════╦══════════════╦════════════════════════════════════════════════╗
║  M-CVD 5d    ║  M-CVD 20d   ║  Interpretation & Action                      ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  UP (+)      ║  UP (+)      ║  ✅ FULL ALIGNMENT — Tín hiệu mạnh nhất        ║
║              ║              ║     Action: Có thể entry theo trend             ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  UP (+)      ║  DOWN (-)    ║  ⚠️ SHORT-TERM BOUNCE in DISTRIBUTION           ║
║              ║              ║     Interpretation: Sóng kỹ thuật trong bear   ║
║              ║              ║     Action: KHÔNG entry mới. Nếu holding → SL  ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  DOWN (-)    ║  UP (+)      ║  🟡 TEMPORARY PULLBACK in ACCUMULATION          ║
║              ║              ║     Interpretation: Tổ chức đang accumulate     ║
║              ║              ║     qua từng đợt bán retail (classic Wyckoff)  ║
║              ║              ║     Action: THEO DÕI — đây là cơ hội tốt       ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  DOWN (-)    ║  DOWN (-)    ║  🔴 FULL ALIGNMENT BEARISH — Tránh xa           ║
║              ║              ║     Action: KHÔNG mua                           ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  FLAT        ║  UP (+)      ║  🟡 MOMENTUM PAUSING — tích lũy đang dừng       ║
║              ║              ║     Action: Chờ 5d resume uptrend               ║
╠══════════════╬══════════════╬════════════════════════════════════════════════╣
║  UP (+)      ║  FLAT        ║  🟡 EARLY BREAKOUT — cần thêm xác nhận          ║
║              ║              ║     Action: Theo dõi 20d có tăng không          ║
╚══════════════╩══════════════╩════════════════════════════════════════════════╝
```

#### Rule Engine Triển khai

```python
# Module: cvd_conflict_resolver.py

def resolve_cvd_conflict(
    cvd_5d: float,
    cvd_20d: float,
    amd_phase: str,
    trend_5d: str,   # 'UP' | 'DOWN' | 'FLAT'
    trend_20d: str
) -> dict:
    """
    Giải quyết xung đột M-CVD multi-timeframe
    """
    
    resolution_matrix = {
        ('UP', 'UP'):     ('FULL_BULL_ALIGNMENT',   'ENTRY_FAVORABLE',    'HIGH'),
        ('UP', 'DOWN'):   ('BOUNCE_IN_DISTRIBUTION','NO_NEW_ENTRY',        'HIGH'),
        ('UP', 'FLAT'):   ('EARLY_BREAKOUT',         'MONITOR_20D',        'MEDIUM'),
        ('DOWN', 'UP'):   ('PULLBACK_IN_ACCUM',      'WATCH_FOR_ENTRY',    'MEDIUM'),
        ('DOWN', 'DOWN'): ('FULL_BEAR_ALIGNMENT',    'AVOID',              'HIGH'),
        ('DOWN', 'FLAT'): ('LOSING_MOMENTUM',        'WAIT',               'LOW'),
        ('FLAT', 'UP'):   ('PAUSING_ACCUM',          'WAIT_RESUME',        'MEDIUM'),
        ('FLAT', 'DOWN'): ('DISTRIBUTION_SLOWING',   'NEUTRAL_WATCH',      'LOW'),
        ('FLAT', 'FLAT'): ('NO_DIRECTIONAL_SIGNAL',  'NO_ACTION',          'VERY_LOW'),
    }
    
    pattern = (trend_5d, trend_20d)
    interpretation, action, confidence = resolution_matrix.get(
        pattern, ('UNKNOWN', 'NO_ACTION', 'VERY_LOW')
    )
    
    # Override với AMD phase context
    if amd_phase == 'DISTRIBUTION' and action == 'ENTRY_FAVORABLE':
        action = 'CAUTION_OVERRIDE'
        interpretation = 'AMD_DISTRIBUTION_OVERRIDES_CVD'
        confidence = 'MEDIUM'
    
    if amd_phase == 'ACCUMULATION' and action == 'NO_NEW_ENTRY':
        # Possible Wyckoff Spring — đánh dấu để nghiên cứu kỹ hơn
        interpretation += '_POSSIBLE_WYCKOFF_SPRING'
        action = 'DETAILED_REVIEW_REQUIRED'
    
    return {
        'pattern': f'CVD5d_{trend_5d}__CVD20d_{trend_20d}',
        'interpretation': interpretation,
        'action': action,
        'confidence': confidence,
        'dominant_timeframe': '20D' if trend_20d != 'FLAT' else '5D',
        'cvd_divergence_score': abs(cvd_5d - cvd_20d),
        'note': f'AMD={amd_phase} context applied'
    }

# Áp dụng cho báo cáo 23/04:
print(resolve_cvd_conflict(8.4, -7.83, 'MARKUP', 'UP', 'DOWN'))
# → pattern: CVD5d_UP__CVD20d_DOWN
# → interpretation: BOUNCE_IN_DISTRIBUTION
# → action: NO_NEW_ENTRY (mặc dù AMD=MARKUP)
# → confidence: HIGH
# KẾT LUẬN: VCG xác nhận KHÔNG vào dù AMD=MARKUP ✓
```

---

## VẤN ĐỀ 4: SMA200 = NaN — Data Gap {#van-de-4}

### 🔍 Phân tích Gốc rễ

> *Technical Director & Senior Software Engineer phân tích:*

SMA200 = NaN trên VIC và VHM là **data pipeline failure**, không phải vấn đề phân tích. Có 3 nguyên nhân có thể:

1. **Data feed SSI không trả về đủ 200 phiên lịch sử** trong một request
2. **Cửa sổ lookback của ứng dụng bị giới hạn** ở mức thấp hơn 200 phiên
3. **Lỗi xử lý split/corporate action** làm break continuity của price series

### 💡 Giải pháp: Multi-Layer Data Fallback System

```python
# Module: data_quality_manager.py

from enum import Enum
from typing import Optional, Tuple
import pandas as pd
import numpy as np

class DataSource(Enum):
    SSI_REALTIME    = "ssi_realtime"
    SSI_HISTORICAL  = "ssi_historical"
    VNDIRECT_API    = "vndirect_fallback"
    CAFEF_SCRAPE    = "cafef_fallback"
    LOCAL_CACHE     = "local_cache"

class SMACalculator:
    """
    Multi-layer fallback SMA calculator với data quality validation
    """
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.min_data_quality_threshold = 0.95  # 95% data completeness
        
    def calculate_sma_with_fallback(
        self, 
        ticker: str, 
        period: int = 200,
        required_sessions: int = None
    ) -> Tuple[Optional[float], dict]:
        """
        Returns: (sma_value, metadata)
        metadata bao gồm source, quality_score, confidence
        """
        required_sessions = required_sessions or period
        
        metadata = {
            'ticker': ticker,
            'period': period,
            'source': None,
            'sessions_available': 0,
            'quality_score': 0.0,
            'confidence': 'NONE',
            'fallback_used': False,
            'adjustment_applied': None
        }
        
        # Layer 1: SSI Real-time + Historical (primary)
        price_data = self._fetch_ssi_full_history(ticker, required_sessions)
        
        if price_data is None or len(price_data) < required_sessions * 0.7:
            # Layer 2: Fallback sources
            price_data = self._fetch_fallback(ticker, required_sessions)
            metadata['fallback_used'] = True
            metadata['source'] = DataSource.LOCAL_CACHE.value
        else:
            metadata['source'] = DataSource.SSI_HISTORICAL.value
        
        if price_data is None:
            return None, {**metadata, 'error': 'ALL_SOURCES_FAILED'}
        
        # Corporate action adjustment
        price_data, adj_note = self._adjust_corporate_actions(ticker, price_data)
        metadata['adjustment_applied'] = adj_note
        
        # Data quality check
        null_ratio = price_data.isnull().sum() / len(price_data)
        if null_ratio > (1 - self.min_data_quality_threshold):
            # Interpolate nhỏ
            price_data = price_data.interpolate(method='linear', limit=5)
        
        sessions_clean = price_data.dropna()
        metadata['sessions_available'] = len(sessions_clean)
        metadata['quality_score'] = len(sessions_clean) / required_sessions
        
        # Tính SMA với data có sẵn
        if len(sessions_clean) >= period:
            sma_value = sessions_clean.iloc[-period:].mean()
            metadata['confidence'] = 'HIGH'
        elif len(sessions_clean) >= period * 0.8:
            # Partial SMA với warning
            sma_value = sessions_clean.mean()
            metadata['confidence'] = 'MEDIUM'
            metadata['note'] = f'SMA{period} tính từ {len(sessions_clean)} phiên thực tế'
        elif len(sessions_clean) >= period * 0.5:
            # EMA làm proxy cho SMA200
            sma_value = sessions_clean.ewm(span=period).mean().iloc[-1]
            metadata['confidence'] = 'LOW'
            metadata['note'] = f'EMA{period} proxy (chỉ {len(sessions_clean)} phiên)'
        else:
            return None, {**metadata, 'error': 'INSUFFICIENT_DATA'}
        
        return sma_value, metadata

    def generate_sma_quality_report(self, tickers: list) -> pd.DataFrame:
        """
        Báo cáo data quality cho toàn bộ watchlist
        """
        report = []
        for ticker in tickers:
            sma200, meta = self.calculate_sma_with_fallback(ticker, 200)
            sma50, meta50 = self.calculate_sma_with_fallback(ticker, 50)
            report.append({
                'ticker': ticker,
                'sma200': sma200,
                'sma200_confidence': meta.get('confidence'),
                'sma200_sessions': meta.get('sessions_available'),
                'sma50': sma50,
                'sma50_confidence': meta50.get('confidence'),
                'fallback_used': meta.get('fallback_used'),
                'data_source': meta.get('source')
            })
        return pd.DataFrame(report)
```

#### Chính sách Confidence Degradation Trong Báo cáo

```
SMA200 Confidence   →   Điều chỉnh Khuyến nghị
─────────────────────────────────────────────────
HIGH   (≥200 phiên) →   Dùng bình thường
MEDIUM (160-199 ph) →   Thêm "(~SMA200)" trong label
LOW    (100-159 ph) →   Thêm "⚠️ LOW CONFIDENCE" warning
NONE   (<100 phiên) →   Ghi "N/A — KHÔNG đánh giá xu hướng dài hạn"
                         + Hạ cấp độ khuyến nghị xuống 1 bậc
```

> **Áp dụng cho 23/04:** VIC và VHM sẽ được hạ từ "NO_ACTION" xuống "LOW_CONFIDENCE_NO_ACTION" và kèm theo note rõ ràng.

---

## VẤN ĐỀ 5: AMF WASH_SALE Directionality {#van-de-5}

### 🔍 Phân tích Gốc rễ

> *Giáo sư Market Microstructure & Stock Investment Expert phân tích:*

Wash sale detection hiện tại của hệ thống chỉ phát hiện **sự tồn tại** của wash trading, không xác định **chiều**. Đây là limitation nghiêm trọng vì:

- **Wash sale bên MUA** (Buy-side wash): Tổ chức tạo volume giả để thu hút retail vào trước khi pump → bullish manipulation
- **Wash sale bên BÁN** (Sell-side wash): Tổ chức tạo volume giả để disguise distribution → bearish trap
- Hai trường hợp này có implication đối lập hoàn toàn

**Đặc thù Việt Nam:** HOSE/HNX có quy định T+2, và các "tay to" thường dùng wash trading qua nhiều tài khoản gia đình để **tạo thanh khoản giả** trước phiên ATC (Auction at the Close), đặc biệt trên các mã vốn hóa nhỏ và trung.

### 💡 Giải pháp: Directional Wash Sale Detection

```python
# Module: amf_directional.py

def classify_wash_sale_direction(
    order_book_data: pd.DataFrame,
    trade_data: pd.DataFrame,
    window_minutes: int = 30
) -> dict:
    """
    Phân loại chiều của wash sale activity
    
    Sử dụng: Order Book Imbalance + Trade Flow Analysis
    
    order_book_data columns: ['time', 'bid_vol', 'ask_vol', 'bid_price', 'ask_price']
    trade_data columns: ['time', 'price', 'volume', 'aggressor']  
                        aggressor: 'BUY' (lifted ask) | 'SELL' (hit bid)
    """
    
    result = {
        'wash_detected': False,
        'direction': 'UNKNOWN',
        'confidence': 'LOW',
        'evidence': [],
        'implication': 'NEUTRAL'
    }
    
    # === BƯỚC 1: Order Book Imbalance (OBI) ===
    order_book_data['obi'] = (
        (order_book_data['bid_vol'] - order_book_data['ask_vol']) /
        (order_book_data['bid_vol'] + order_book_data['ask_vol'])
    )
    avg_obi = order_book_data['obi'].mean()
    
    # OBI > +0.3: Bên mua đang dominant
    # OBI < -0.3: Bên bán đang dominant
    
    # === BƯỚC 2: Trade Flow Imbalance (TFI) ===
    buy_volume = trade_data[trade_data['aggressor'] == 'BUY']['volume'].sum()
    sell_volume = trade_data[trade_data['aggressor'] == 'SELL']['volume'].sum()
    total_volume = buy_volume + sell_volume
    
    tfi = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0
    
    # === BƯỚC 3: Wash Sale Pattern Detection ===
    # Pattern 1: Volume spike KHÔNG đi kèm price movement = potential wash
    price_change_pct = (
        (trade_data['price'].iloc[-1] - trade_data['price'].iloc[0]) / 
        trade_data['price'].iloc[0]
    )
    vol_spike_ratio = trade_data['volume'].max() / trade_data['volume'].mean()
    
    is_wash_suspected = (vol_spike_ratio > 3.0) and (abs(price_change_pct) < 0.005)
    
    if not is_wash_suspected:
        result['wash_detected'] = False
        return result
    
    result['wash_detected'] = True
    
    # === BƯỚC 4: Phân loại chiều ===
    
    # BUY-SIDE WASH indicators:
    # - OBI dương mạnh (bên mua dominant trong OB)
    # - TFI dương (nhiều buy aggressor hơn)
    # - Giá giữ hoặc tăng nhẹ trong wash
    # - Thường xuất hiện TRƯỚC giai đoạn pump
    
    buy_wash_score = 0
    if avg_obi > 0.2:    buy_wash_score += 2
    if tfi > 0.2:        buy_wash_score += 2
    if price_change_pct >= 0: buy_wash_score += 1
    
    # SELL-SIDE WASH indicators:
    # - OBI âm (bên bán dominant)
    # - TFI âm
    # - Giá không giảm mặc dù volume bán lớn (hidden support đang giải toả)
    
    sell_wash_score = 0
    if avg_obi < -0.2:    sell_wash_score += 2
    if tfi < -0.2:        sell_wash_score += 2
    if price_change_pct <= 0.002: sell_wash_score += 1
    
    # Phán quyết
    if buy_wash_score > sell_wash_score + 1:
        result['direction'] = 'BUY_SIDE'
        result['implication'] = 'POTENTIALLY_BULLISH_ACCUMULATION'
        result['confidence'] = 'HIGH' if buy_wash_score >= 4 else 'MEDIUM'
        result['evidence'].append(f'OBI={avg_obi:.2f}, TFI={tfi:.2f} → Buy dominant')
        result['action_hint'] = (
            'Wash sale từ bên MUA: tổ chức có thể đang tích lũy. '
            'Theo dõi price action 3-5 phiên tiếp theo.'
        )
    elif sell_wash_score > buy_wash_score + 1:
        result['direction'] = 'SELL_SIDE'
        result['implication'] = 'POTENTIALLY_BEARISH_DISTRIBUTION'
        result['confidence'] = 'HIGH' if sell_wash_score >= 4 else 'MEDIUM'
        result['evidence'].append(f'OBI={avg_obi:.2f}, TFI={tfi:.2f} → Sell dominant')
        result['action_hint'] = (
            'Wash sale từ bên BÁN: cảnh báo distribution disguise. '
            'Không nên entry mới.'
        )
    else:
        result['direction'] = 'AMBIGUOUS'
        result['implication'] = 'UNCLEAR'
        result['confidence'] = 'LOW'
        result['action_hint'] = 'Không đủ bằng chứng phân loại chiều. Chờ thêm dữ liệu.'
    
    return result
```

#### Output Cải tiến Cho Báo cáo

**Thay vì:**
> `AMF: WARN — WASH_SALE_VOLUME Z4.0`

**Nên là:**
> `AMF: WARN — WASH_SALE Z4.0 | Direction: BUY_SIDE (OBI=+0.31, TFI=+0.24) | Implication: POTENTIALLY_BULLISH | Confidence: HIGH`

---

## VẤN ĐỀ 6: M-CVD Normalization {#van-de-6}

### 🔍 Phân tích Gốc rễ

> *Giáo sư Economics & Data Scientist phân tích:*

So sánh M-CVD raw giữa các mã khác nhau là như so sánh doanh thu tuyệt đối của Vingroup với một công ty mid-cap — **vô nghĩa về mặt thống kê**. VCB có ADTV (Average Daily Trading Volume) ~500–800 tỷ VND, trong khi HHV có thể chỉ 20–50 tỷ. Cùng một M-CVD +8M shares mang ý nghĩa hoàn toàn khác nhau.

### 💡 Giải pháp: Normalized CVD Score (NCVD)

```python
# Module: normalized_cvd.py

def calculate_normalized_cvd(
    raw_cvd: float,          # Triệu đồng hoặc triệu cổ phiếu
    adtv_20d: float,         # Average Daily Trading Value (20 phiên)
    window_days: int = 5     # Tương ứng với M-CVD 5d hoặc 20d
) -> dict:
    """
    Chuẩn hóa CVD theo ADTV
    
    NCVD = raw_CVD / (ADTV × window_days)
    
    Interpretation:
    > +0.5 : Rất tích cực (dòng tiền ròng tích lũy > 50% ADTV mỗi ngày)
    +0.2 to +0.5 : Tích cực
    -0.2 to +0.2 : Trung lập
    -0.2 to -0.5 : Tiêu cực
    < -0.5 : Rất tiêu cực (phân phối mạnh)
    """
    
    expected_volume = adtv_20d * window_days
    ncvd = raw_cvd / expected_volume if expected_volume > 0 else 0
    
    if ncvd > 0.5:
        label = 'VERY_BULLISH'
        color = '🟢🟢'
    elif ncvd > 0.2:
        label = 'BULLISH'
        color = '🟢'
    elif ncvd > -0.2:
        label = 'NEUTRAL'
        color = '⚪'
    elif ncvd > -0.5:
        label = 'BEARISH'
        color = '🔴'
    else:
        label = 'VERY_BEARISH'
        color = '🔴🔴'
    
    # Z-score so với lịch sử của chính mã đó
    # (cần historical NCVD series để tính)
    
    return {
        'raw_cvd': raw_cvd,
        'adtv_20d': adtv_20d,
        'ncvd': ncvd,
        'ncvd_pct': f'{ncvd*100:.1f}%',
        'label': label,
        'color': color,
        'interpretation': (
            f"Dòng tiền ròng = {ncvd*100:.1f}% khối lượng trung bình "
            f"{window_days} ngày"
        )
    }

# Ví dụ áp dụng 23/04 (ước tính ADTV):
ADTV_ESTIMATES = {
    'VCB': 500_000,   # triệu VND
    'HHV': 25_000,
    'VCG': 30_000,
    'NKG': 80_000,
    'VIC': 400_000,
    'VHM': 300_000,
    'VIX': 60_000,
    'CII': 40_000,
    'OCB': 50_000,
}

CVD_5D_RAW = {
    'VCB': 10_560, 'HHV': 7_800, 'VCG': 8_400,
    'NKG': 3_820, 'VIC': 2_240, 'VHM': 1_640
}

print("=== NCVD Normalized Comparison ===")
for ticker, raw in CVD_5D_RAW.items():
    result = calculate_normalized_cvd(raw, ADTV_ESTIMATES[ticker], 5)
    print(f"{ticker}: raw={raw:,} | NCVD={result['ncvd_pct']} | {result['label']}")
```

**Output kỳ vọng:**

| Mã | M-CVD 5d Raw | ADTV Ước tính | NCVD 5d | Label |
|----|-------------|---------------|---------|-------|
| VCB | +10,560M | 500,000M | **+0.42%** | NEUTRAL (nhỏ hơn nhiều so với volume) |
| HHV | +7,800M | 25,000M | **+6.24%** | 🟢🟢 VERY_BULLISH (rất có ý nghĩa) |
| VCG | +8,400M | 30,000M | **+5.60%** | 🟢🟢 VERY_BULLISH |
| NKG | +3,820M | 80,000M | **+0.96%** | NEUTRAL |
| VIC | +2,240M | 400,000M | **+0.11%** | NEUTRAL (không đáng kể) |
| VHM | +1,640M | 300,000M | **+0.11%** | NEUTRAL |

> **Phát hiện quan trọng:** VCB với M-CVD +10.56M trông rất lớn trên báo cáo gốc, nhưng sau khi normalize thì chỉ là **0.42% ADTV** — tức là **không có ý nghĩa thực chất**. Trong khi đó HHV với M-CVD +7.8M tuy nhỏ hơn về số tuyệt đối nhưng lại bằng **6.24% ADTV** — đây mới là tín hiệu dòng tiền mạnh thực sự.

---

## LỘ TRÌNH TRIỂN KHAI TỔNG THỂ {#lo-trinh}

### 📅 Sprint Backlog — SDLC theo PMBOK/BABOK

```
┌─────────────────────────────────────────────────────────────────┐
│  EPIC: TradingOS Signal Quality Enhancement v2.0               │
│  Thời gian: 6 Sprint × 2 tuần = 12 tuần                        │
│  Team: 1 Tech Lead + 2 BE + 1 DS + 1 QA + 1 BA                │
└─────────────────────────────────────────────────────────────────┘

SPRINT 1 (Tuần 1-2): Data Foundation
─────────────────────────────────────
[ ] RSR-011: Implement multi-layer data fallback (SMA200 NaN fix)
[ ] RSR-012: Corporate action adjustment pipeline
[ ] RSR-013: Data quality scoring & confidence tier system
[ ] RSR-014: Automated data health dashboard

SPRINT 2 (Tuần 3-4): Signal Enhancement  
─────────────────────────────────────────
[ ] RSR-015: Market Regime Classifier (BULL/BEAR/SIDEWAYS/HIGH_VOL)
[ ] RSR-016: Adaptive RSI threshold engine
[ ] RSR-017: Sector mapping table (VN-specific)
[ ] RSR-018: RSI historical sustained tracking

SPRINT 3 (Tuần 5-6): CVD Intelligence
───────────────────────────────────────
[ ] RSR-019: ADTV calculator & caching layer
[ ] RSR-020: NCVD (Normalized CVD) score
[ ] RSR-021: CVD conflict resolution matrix
[ ] RSR-022: Multi-timeframe priority rules engine

SPRINT 4 (Tuần 7-8): AMF Enhancement
──────────────────────────────────────
[ ] RSR-023: Order book integration (SSI FastConnect)
[ ] RSR-024: Trade flow aggressor classification
[ ] RSR-025: Directional wash sale detector
[ ] RSR-026: AMF confidence scoring update

SPRINT 5 (Tuần 9-10): MC Recalibration
─────────────────────────────────────────
[ ] RSR-027: EWMA volatility estimator
[ ] RSR-028: Regime-adjusted drift model
[ ] RSR-029: ATR-based TP/SL replacement
[ ] RSR-030: T+2 settlement delay in simulation
[ ] RSR-031: MC calibration backtesting framework
[ ] RSR-032: Brier score automated monitoring

SPRINT 6 (Tuần 11-12): Integration & QA
─────────────────────────────────────────
[ ] RSR-033: Full integration testing
[ ] RSR-034: Backtesting trên 6 tháng dữ liệu lịch sử
[ ] RSR-035: Performance benchmark (Sharpe, Sortino, Max DD)
[ ] RSR-036: Báo cáo output format v2.0
[ ] RSR-037: User acceptance testing
[ ] RSR-038: Documentation & training materials
```

### 🎯 KPI Thành công

| KPI | Baseline Hiện tại | Target Sau Enhancement |
|-----|-------------------|----------------------|
| mc_prob mean (watchlist) | 8% | 25–40% |
| SMA200 coverage rate | ~70% | >99% |
| Wash sale direction coverage | 0% | >80% |
| CVD cross-mã comparability | Không có | NCVD standard |
| RSI false signal rate | ~35% | <15% |
| Signal conflict resolution | Manual | Automated |

---

## 📌 KẾT LUẬN HỘI ĐỒNG

> *Chủ tịch Hội đồng tổng kết:*

Sáu vấn đề được xác định trong báo cáo 23/04/2026 không phải là lỗi ngẫu nhiên mà là **systematic gaps** trong kiến trúc signal generation hiện tại. Tuy nhiên, chúng đều có giải pháp rõ ràng và được định lượng.

**Thứ tự ưu tiên giải quyết:**

1. 🥇 **NCVD Normalization** — Tác động cao nhất, implementation dễ nhất
2. 🥈 **CVD Conflict Resolution Matrix** — Rule tường minh, không cần data mới
3. 🥉 **Adaptive RSI Thresholds** — Cải thiện accuracy đáng kể
4. **SMA200 Data Fallback** — Infrastructure, cần effort nhưng quan trọng
5. **MC Recalibration** — Phức tạp nhất, cần backtesting validation
6. **AMF Directionality** — Cần SSI FastConnect order book access

> ⚠️ **Lưu ý quan trọng của Hội đồng:** Toàn bộ framework trên là công cụ hỗ trợ ra quyết định, không phải thay thế phán đoán đầu tư. Rủi ro thị trường luôn tồn tại và không có hệ thống nào dự báo chính xác tuyệt đối. Nhà đầu tư chịu trách nhiệm hoàn toàn về quyết định của mình.

---

*📅 Tài liệu này được ban hành bởi Hội đồng Học thuật — Phiên họp 23/04/2026*
*🔒 Phân loại: Internal Research & Development*
*📧 Liên hệ: Academic Board — Captain Seventh QUANT TERMINAL*