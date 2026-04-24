"""Shared T+ verdict formatting for Scanner and Audit views."""
from __future__ import annotations

import math


TPLUS_MAPPING_GUIDE = """
| Action | T+ Verdict | Nghia nhanh |
|---|---|---|
| STRONG_BUY / BUY | MUA_NGAY | Tin hieu tong the va timing T+ dong thuan, co the vao trong vung entry.
| STRONG_BUY / BUY | CHO_XAC_NHAN | Nen co ban on, nhung timing chua du sach; cho xac nhan dong tien hay breakout.
| WATCH | MUA_NGAY | Timing ngan han on nhung xac suat tong the chua du manh; chi nen tham do nho.
| BAT KY Action mua | THEO_DOI | Co setup nhung chua du diem vao; uu tien quan sat thay vi duoi gia.
| BAT KY Action mua | TRANH_XA | T+ danh gia diem vao xau, khong nen mo vi the moi du Action chua xau.
| EXIT / FORCED_EXIT | BAT KY Verdict | Uu tien quan tri rui ro va thoat lenh, khong de T+ override Action.
"""

_VERDICT_LABELS = {
    "MUA_NGAY": "Mua ngay",
    "CHO_XAC_NHAN": "Cho xac nhan",
    "THEO_DOI": "Theo doi",
    "TRANH_XA": "Tranh xa",
}

_VERDICT_STYLES = {
    "MUA_NGAY": "background-color:#0f5132; color:#d1f7e5; font-weight:bold",
    "CHO_XAC_NHAN": "background-color:#664d03; color:#fff3cd; font-weight:bold",
    "THEO_DOI": "background-color:#055160; color:#cff4fc; font-weight:bold",
    "TRANH_XA": "background-color:#842029; color:#f8d7da; font-weight:bold",
}

_VERDICT_ROW_TINT = {
    "MUA_NGAY": "background-color:#22c55e11",
    "CHO_XAC_NHAN": "background-color:#f59e0b14",
    "THEO_DOI": "background-color:#0ea5e914",
    "TRANH_XA": "background-color:#ef444414",
}


def _as_price(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number <= 0:
        return None
    return number


def _price_text(value: float | int | None) -> str:
    number = _as_price(value)
    if number is None:
        return "-"
    return f"{number:,.1f}"


def verdict_style(verdict: str) -> str:
    return _VERDICT_STYLES.get(verdict or "", "")


def verdict_row_tint(verdict: str) -> str:
    return _VERDICT_ROW_TINT.get(verdict or "", "")


def verdict_label(verdict: str, verdict_vi: str = "") -> str:
    return verdict_vi or _VERDICT_LABELS.get(verdict or "", verdict or "")


def build_action_tplus_explanation(action: str, verdict: str) -> str:
    action = (action or "").upper()
    verdict = (verdict or "").upper()

    if action in {"EXIT", "FORCED_EXIT"}:
        return "Action uu tien thoat vi the; T+ chi dung de tham chieu muc stop/target, khong mo vi the moi."
    if action == "NO_ACTION":
        if verdict == "MUA_NGAY":
            return "Timing ngan han co the tam on nhung tong diem chua dat; dung ngoai hoac chi quan sat them."
        if verdict == "CHO_XAC_NHAN":
            return "Nen dung ngoai. T+ cho thay can them xac nhan, trong khi Action chua ung ho mua."
        if verdict == "TRANH_XA":
            return "Ca Action va T+ deu khong ung ho mua moi; uu tien bao toan von."
        return "Chua co dong thuan giua chat luong tin hieu va timing; tiep tuc theo doi."

    if verdict == "MUA_NGAY":
        if action in {"STRONG_BUY", "BUY"}:
            return "Tin hieu tong the tot va timing T+ dong thuan; co the giai ngan trong vung entry neu quan tri dung stop."
        return "Timing T+ on nhung Action moi o muc theo doi; chi nen vao tham do nho neu chap nhan rui ro."

    if verdict == "CHO_XAC_NHAN":
        if action in {"STRONG_BUY", "BUY"}:
            return "Nen co ban tot nhung chua den diem kich hoat dep; cho breakout, dong tien vao lai hoac gia giu vung entry."
        return "Co manh moi quan sat nhung chua du xac suat de vao lenh; uu tien cho them xac nhan."

    if verdict == "TRANH_XA":
        return "Khong duoi gia. Du Action chua xau, T+ cho thay diem vao hien tai bat loi va reward/risk kem."

    if action == "WATCH":
        return "Cau truc dang theo doi, chua co diem vao dep ngay luc nay."
    return "Tin hieu tong the chua du ro; tiep tuc quan sat cho den khi T+ va Action dong thuan hon."


def build_tplus_exit_plan(
    verdict: str,
    stop: float | int | None,
    target_t25: float | int | None,
    target_t5: float | int | None,
    entry_low: float | int | None = None,
    entry_high: float | int | None = None,
) -> str:
    verdict = (verdict or "").upper()
    stop_text = _price_text(stop)
    t25_text = _price_text(target_t25)
    t5_text = _price_text(target_t5)
    low_text = _price_text(entry_low)
    high_text = _price_text(entry_high)

    if low_text != "-" and high_text != "-":
        entry_text = f"Vung vao {low_text}-{high_text}. "
    else:
        entry_text = ""

    plan_text = f"SL {stop_text} | T+2.5 {t25_text} | T+5 {t5_text}"

    if verdict == "MUA_NGAY":
        return f"{entry_text}Mua duoc neu gia nam trong vung cho phep. {plan_text}"
    if verdict == "CHO_XAC_NHAN":
        return f"Chua vao ngay. Khi co xac nhan, tham chieu ke hoach: {plan_text}"
    if verdict == "TRANH_XA":
        return f"Tranh mo vi the moi. Neu dang nam giu, dung {plan_text} lam moc quan tri rui ro."
    return f"Theo doi them truoc khi kich hoat lenh. Ke hoach du kien: {plan_text}"