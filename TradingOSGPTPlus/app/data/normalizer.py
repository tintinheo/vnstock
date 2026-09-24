from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.data.universe import lookup_exchange, normalize_ticker

PRICE_ALIASES = {
    "date": ["date", "tradingdate", "ngay", "ngày", "time", "trading_date"],
    "open": ["open", "openprice", "gia mo cua", "giá mở cửa", "mo cua", "mở cửa", "openingprice", "o"],
    "high": ["high", "highestprice", "cao nhat", "cao nhất", "gia cao nhat", "giá cao nhất", "h"],
    "low": ["low", "lowestprice", "thap nhat", "thấp nhất", "gia thap nhat", "giá thấp nhất", "l"],
    "close": [
        "close",
        "closeprice",
        "matchprice",
        "lastprice",
        "gia dong cua",
        "giá đóng cửa",
        "dong cua",
        "đóng cửa",
        "c",
    ],
    "volume": [
        "volume",
        "totalvolume",
        "totalmatchvol",
        "totalmatchvolume",
        "khoi luong",
        "khối lượng",
        "kl khop lenh",
        "kl khớp lệnh",
        "vol",
        "v",
    ],
    "value": ["value", "totalvalue", "totalmatchvalue", "gia tri", "giá trị", "gtgd"],
}


def normalize_ohlcv(raw: pd.DataFrame, ticker: str, source: str, unit_rule: str | None = None) -> pd.DataFrame:
    normalized_ticker = normalize_ticker(ticker)
    if raw.empty:
        raise ValueError(f"{source} returned an empty dataframe")

    frame = raw.copy()
    frame.columns = [str(col).strip() for col in frame.columns]
    renamed = _rename_columns(frame)
    missing = {"date", "open", "high", "low", "close", "volume"} - set(renamed.columns)
    if missing:
        raise ValueError(f"{source} missing columns: {', '.join(sorted(missing))}")

    out = renamed[["date", "open", "high", "low", "close", "volume"]].copy()
    out["value"] = renamed["value"] if "value" in renamed.columns else None
    out["date"] = _to_date(out["date"])
    for column in ["open", "high", "low", "close", "value"]:
        out[column] = _to_number(out[column])
    out["volume"] = _to_number(out["volume"]).fillna(0).astype("int64")
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    if out.empty:
        raise ValueError(f"{source} had no valid OHLCV rows after parsing")

    resolved_rule = unit_rule or _source_default_rule(source)
    out, applied_rule = apply_price_unit_rule(out, resolved_rule)
    validate_ohlcv(out, source)
    fetched_at = datetime.now(timezone.utc)
    out["ticker"] = normalized_ticker
    out["exchange"] = lookup_exchange(normalized_ticker)
    out["source"] = source
    out["adjusted"] = False
    out["fetched_at"] = fetched_at
    out["unit_rule_applied"] = applied_rule
    ordered = [
        "ticker",
        "exchange",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "value",
        "source",
        "adjusted",
        "fetched_at",
        "unit_rule_applied",
    ]
    return out[ordered]


def apply_price_unit_rule(frame: pd.DataFrame, rule: str) -> tuple[pd.DataFrame, str]:
    out = frame.copy()
    price_columns = ["open", "high", "low", "close"]
    applied = rule
    if rule == "thousands_to_vnd":
        out[price_columns] = out[price_columns] * 1000
        if out["value"].notna().any() and out["value"].median() < 1_000_000_000:
            out["value"] = out["value"] * 1000
    elif rule == "divide_1000":
        out[price_columns] = out[price_columns] / 1000
    elif rule == "auto_detect":
        median_close = float(out["close"].median())
        if median_close < 500:
            out[price_columns] = out[price_columns] * 1000
            applied = "auto_detect:thousands_to_vnd"
        elif median_close > 1_000_000:
            out[price_columns] = out[price_columns] / 1000
            applied = "auto_detect:divide_1000"
        else:
            applied = "auto_detect:actual_vnd"
    elif rule != "actual_vnd":
        raise ValueError(f"unsupported price unit rule: {rule}")
    return out, applied


def validate_ohlcv(frame: pd.DataFrame, source: str) -> None:
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"{source} produced non-positive prices")
    if (frame["high"] < frame[["open", "close"]].max(axis=1)).any():
        raise ValueError(f"{source} produced invalid high/open/close relationship")
    if (frame["low"] > frame[["open", "close"]].min(axis=1)).any():
        raise ValueError(f"{source} produced invalid low/open/close relationship")
    if (frame["volume"] < 0).any():
        raise ValueError(f"{source} produced negative volume")
    median_close = float(frame["close"].median())
    if not 500 <= median_close <= 1_000_000:
        raise ValueError(f"{source} median close {median_close:,.0f} is implausible after normalization")


def _rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    key_by_col = {_clean_column_name(col): col for col in frame.columns}
    rename_map: dict[str, str] = {}
    for canonical, aliases in PRICE_ALIASES.items():
        for alias in aliases:
            cleaned_alias = _clean_column_name(alias)
            if cleaned_alias in key_by_col:
                rename_map[key_by_col[cleaned_alias]] = canonical
                break
    return frame.rename(columns=rename_map)


def _clean_column_name(value: Any) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(".", "")
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def _to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("--", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _to_date(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    yyyymmdd = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if yyyymmdd.any():
        parsed.loc[yyyymmdd] = pd.to_datetime(text.loc[yyyymmdd], format="%Y%m%d", errors="coerce")
    return parsed.dt.date


def _source_default_rule(source: str) -> str:
    source_lower = source.lower()
    if source_lower == "kbs":
        return "actual_vnd"
    if source_lower == "cafef":
        return "thousands_to_vnd"
    return "auto_detect"
