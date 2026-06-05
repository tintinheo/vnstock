from typing import Dict, List

FACTOR_LABELS = {
    "wyckoff_spring": "Spring Wyckoff",
    "zvol": "Volume đột biến",
    "vwap": "Giá > VWAP",
    "vcp": "VCP nén biến động",
    "rsi_crossup": "RSI cắt lên",
    "bullish_div": "Phân kỳ tăng RSI",
    "vqs": "Chất lượng volume (VQS)",
    "cvd_whale": "Cá voi mua ròng (CVD)",
    "vsa_no_supply": "VSA No Supply",
    "vsa_no_demand": "VSA No Demand (rủi ro)",
    "fol": "Dòng tiền ngoại",
    "amd_accum": "AMD: Tích lũy",
    "canslim": "CAN SLIM thấp",
    "mcvd": "M-CVD tích lũy",
    "delta_div": "Delta Divergence (rủi ro)"
}

def generate_shap_explanation(mfpm_components: Dict[str, int]) -> List[str]:
    """
    Explains the top contributing factors to the MFPM score.
    Returns the top 5 factors formatted for the UI.
    """
    # Sort by absolute impact weight
    sorted_factors = sorted(mfpm_components.items(), key=lambda x: abs(x[1]), reverse=True)
    
    explanations = []
    for k, v in sorted_factors[:5]:
        icon = '✅' if v > 0 else '⚠️'
        sign = '+' if v > 0 else ''
        label = FACTOR_LABELS.get(k, k)
        explanations.append(f"{icon} {label}: {sign}{v}")
        
    return explanations

def generate_advisory_text(signal: dict) -> str:
    """
    Generates the final Vietnamese advisory text using the FR-1 template.
    """
    ticker = signal.get("ticker", "UNKNOWN")
    price = signal.get("entry_price", 0)
    action = signal.get("action", "WATCH")
    mode = signal.get("mode", "MODE_A")
    sl = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    tp2 = signal.get("tp2", 0)
    sms = signal.get("sms", 0)
    sms_label = signal.get("sms_label", "NEUTRAL")
    shap = " | ".join(signal.get("shap_top5", []))
    
    sl_pct = abs((price - sl) / price) * 100 if price else 0
    tp1_pct = abs((tp1 - price) / price) * 100 if price else 0
    tp2_pct = abs((tp2 - price) / price) * 100 if price else 0
    
    advisory = f"""
{ticker} @ {price:,.0f} VND:

📊 Dòng tiền: {sms_label} | SMS={sms}/100 
HMM: {signal.get('hmm_state', 'UNKNOWN')} | Ω={signal.get('gmo_omega', 0.0)}

→ Khuyến nghị {action} ({mode}): Vào {price:,.0f} | SL {sl:,.0f} (-{sl_pct:.1f}%)
→ TP1 {tp1:,.0f} (+{tp1_pct:.1f}%) | TP2 {tp2:,.0f} (+{tp2_pct:.1f}%)
→ MFPM: {signal.get('mfpm_score', 0)}/120 | MC Win: {signal.get('mc_win_prob', 0)*100:.1f}%

Lý do:
{shap}
"""
    return advisory.strip()