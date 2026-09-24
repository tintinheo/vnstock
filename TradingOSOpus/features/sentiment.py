"""features/sentiment.py – Vietnamese financial sentiment analysis (100+ terms)."""
import re

POSITIVE_TERMS = {
    "tăng mạnh": 0.8, "tăng trần": 0.9, "bùng nổ": 0.9, "phi mã": 0.85,
    "đột phá": 0.7, "tích cực": 0.6, "khởi sắc": 0.65, "hồi phục": 0.5,
    "lạc quan": 0.6, "kỷ lục": 0.7, "vượt đỉnh": 0.8, "tăng vốn": 0.5,
    "lãi lớn": 0.8, "lãi ròng": 0.6, "doanh thu tăng": 0.6, "triển vọng": 0.5,
    "cơ hội": 0.5, "thu hút": 0.4, "dòng tiền vào": 0.6, "mua ròng": 0.7,
    "nâng hạng": 0.8, "nới room": 0.6, "giải ngân": 0.5, "cổ tức cao": 0.6,
    "tăng trưởng": 0.6, "phục hồi mạnh": 0.7, "bứt phá": 0.75, "sáng cửa": 0.5,
    "thanh khoản tăng": 0.5, "vốn ngoại đổ vào": 0.7, "FDI tăng": 0.6,
    "GDP tăng": 0.6, "xuất khẩu tăng": 0.5, "lợi nhuận kỷ lục": 0.85,
    "EPS tăng": 0.6, "ROE cao": 0.5, "margin tăng": 0.5, "PE thấp": 0.4,
    "định giá hấp dẫn": 0.6, "cổ phiếu tiềm năng": 0.5, "khuyến nghị mua": 0.7,
    "outperform": 0.6, "upside": 0.5, "bull": 0.6, "breakout": 0.7,
    "golden cross": 0.6, "đảo chiều tăng": 0.7, "hỗ trợ mạnh": 0.5,
    "tín hiệu mua": 0.65, "accumulate": 0.5, "overweight": 0.5,
    "rally": 0.7, "bullish": 0.6, "uptrend": 0.6, "recovery": 0.5,
    "expansion": 0.5, "boom": 0.7, "surge": 0.7, "soar": 0.8,
    "thăng hoa": 0.7, "bền vững": 0.4, "ổn định": 0.3, "an toàn": 0.3,
}

NEGATIVE_TERMS = {
    "giảm mạnh": -0.8, "giảm sàn": -0.9, "sụp đổ": -0.95, "lao dốc": -0.85,
    "bán tháo": -0.9, "tháo chạy": -0.85, "hoảng loạn": -0.9, "bi quan": -0.6,
    "rủi ro": -0.5, "cảnh báo": -0.5, "lo ngại": -0.5, "bất ổn": -0.6,
    "suy thoái": -0.7, "khủng hoảng": -0.8, "phá sản": -0.95, "nợ xấu": -0.7,
    "thua lỗ": -0.7, "lỗ ròng": -0.7, "doanh thu giảm": -0.6, "margin call": -0.8,
    "bán ròng": -0.6, "vốn ngoại rút": -0.7, "lãi suất tăng": -0.5,
    "lạm phát tăng": -0.5, "thắt chặt": -0.5, "siết tín dụng": -0.6,
    "căng thẳng": -0.5, "chiến tranh thương mại": -0.6, "trừng phạt": -0.5,
    "downgrade": -0.6, "underperform": -0.5, "sell": -0.5, "bear": -0.6,
    "death cross": -0.7, "breakdown": -0.7, "tín hiệu bán": -0.65,
    "kháng cự mạnh": -0.4, "downtrend": -0.6, "bearish": -0.6,
    "correction": -0.4, "crash": -0.9, "recession": -0.7, "plunge": -0.8,
    "dump": -0.7, "đình trệ": -0.5, "trì trệ": -0.4, "ảm đạm": -0.5,
    "tiêu cực": -0.6, "xấu": -0.4, "giảm điểm": -0.5, "mất mát": -0.6,
}

INTENSIFIERS = {"rất": 1.5, "cực kỳ": 1.8, "vô cùng": 1.7, "hết sức": 1.5,
    "đặc biệt": 1.3, "mạnh mẽ": 1.4, "significantly": 1.4, "extremely": 1.8}
NEGATORS = {"không": -1, "chưa": -0.8, "chẳng": -1, "không hề": -1.2, "never": -1}

class VietnameseFinancialSentiment:
    def __init__(self):
        self.positive = POSITIVE_TERMS
        self.negative = NEGATIVE_TERMS
        self.intensifiers = INTENSIFIERS
        self.negators = NEGATORS

    def score_text(self, text):
        text_lower = text.lower()
        pos_score, neg_score, matches = 0.0, 0.0, 0
        all_terms = {**self.positive, **self.negative}
        sorted_terms = sorted(all_terms.keys(), key=len, reverse=True)
        for term in sorted_terms:
            if term in text_lower:
                score = all_terms[term]; matches += 1
                multiplier = 1.0
                for intens, mult in self.intensifiers.items():
                    if intens in text_lower: multiplier = max(multiplier, mult)
                for neg, mult in self.negators.items():
                    idx_neg = text_lower.find(neg)
                    idx_term = text_lower.find(term)
                    if idx_neg != -1 and 0 <= idx_term - idx_neg <= len(neg) + 5:
                        score *= mult
                if score > 0: pos_score += score * multiplier
                else: neg_score += abs(score) * multiplier
        total = pos_score + neg_score
        compound = (pos_score - neg_score) / (total + 1e-6) if total > 0 else 0.0
        return {"positive": round(pos_score, 4), "negative": round(neg_score, 4),
                "compound": round(compound, 4), "matches": matches}

    def aggregate_sentiment(self, texts):
        if not texts: return {"positive": 0, "negative": 0, "compound": 0, "count": 0}
        scores = [self.score_text(t) for t in texts]
        n = len(scores)
        return {
            "positive": round(sum(s["positive"] for s in scores) / n, 4),
            "negative": round(sum(s["negative"] for s in scores) / n, 4),
            "compound": round(sum(s["compound"] for s in scores) / n, 4),
            "count": n,
        }