"""Dataframe filtering UI component."""
from __future__ import annotations

import pandas as pd
import streamlit as st
from pandas.api.types import (
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)


def filter_dataframe(df: pd.DataFrame, key_prefix: str = "df_filter") -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns.

    Args:
        df: Original dataframe
        key_prefix: Unique key prefix for streamlit widgets

    Returns:
        The filtered dataframe
    """
    modify = st.checkbox("🔍 Thêm bộ lọc nhiều cột (Advanced Filter)", key=f"{key_prefix}_modify_cb")

    if not modify:
        return df

    df_filtered = df.copy()

    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df_filtered.columns:
        if is_object_dtype(df_filtered[col]):
            try:
                df_filtered[col] = pd.to_datetime(df_filtered[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df_filtered[col]):
            df_filtered[col] = df_filtered[col].dt.tz_localize(None)

    with st.container(border=True):
        to_filter_columns = st.multiselect(
            "Chọn các cột muốn lọc:",
            df_filtered.columns,
            key=f"{key_prefix}_cols_ms"
        )
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("↳")
            
            # Use pandas mapping to determine widget type
            target_series = df_filtered[column]
            
            # Treat boolean or low-cardinality < 10 as categorical
            if (
                isinstance(target_series.dtype, pd.CategoricalDtype)
                or target_series.nunique() < 10
                or target_series.dtype == bool
            ):
                options = target_series.dropna().unique().tolist()
                user_cat_input = right.multiselect(
                    f"Giá trị cho [{column}]",
                    options,
                    default=options,
                    key=f"{key_prefix}_{column}_ms"
                )
                df_filtered = df_filtered[df_filtered[column].isin(user_cat_input)]
            elif is_numeric_dtype(target_series):
                min_v = float(target_series.min())
                max_v = float(target_series.max())
                if min_v == max_v:
                    _ = right.slider(
                        f"Khoảng giá trị [{column}]",
                        min_value=min_v,
                        max_value=max_v+1.0,
                        value=(min_v, max_v+1.0),
                        disabled=True,
                        key=f"{key_prefix}_{column}_sl"
                    )
                else:
                    step = (max_v - min_v) / 100 if max_v > min_v else 0.1
                    user_num_input = right.slider(
                        f"Khoảng giá trị cho [{column}]",
                        min_value=min_v,
                        max_value=max_v,
                        value=(min_v, max_v),
                        step=step,
                        key=f"{key_prefix}_{column}_sl"
                    )
                    df_filtered = df_filtered[df_filtered[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(target_series):
                min_v = target_series.min().to_pydatetime()
                max_v = target_series.max().to_pydatetime()
                user_date_input = right.date_input(
                    f"Khoảng thời gian [{column}]",
                    value=(min_v, max_v),
                    key=f"{key_prefix}_{column}_dt",
                )
                if isinstance(user_date_input, tuple) and len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df_filtered = df_filtered.loc[df_filtered[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Tìm chuỗi trong [{column}]",
                    key=f"{key_prefix}_{column}_txt",
                )
                if user_text_input:
                    df_filtered = df_filtered[df_filtered[column].astype(str).str.contains(user_text_input, case=False, na=False)]

    return df_filtered