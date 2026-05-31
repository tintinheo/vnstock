from __future__ import annotations

from backtest.engine import BacktestResult
from ui.backtest_tab import _backtest_review_summary, _backtest_review_table


def _result(metrics: dict) -> BacktestResult:
    return BacktestResult(ticker="VCB", timeframe="1M", metrics=metrics)


def test_backtest_review_table_ranks_stronger_timeframe_first():
    results = {
        "1W": _result({
            "cagr": 8.0,
            "total_return": 12.0,
            "sharpe": 0.9,
            "max_dd": -10.0,
            "win_rate": 58.0,
            "profit_factor": 1.2,
            "n_trades": 5,
        }),
        "1M": _result({
            "cagr": 18.0,
            "total_return": 25.0,
            "sharpe": 1.5,
            "max_dd": -8.0,
            "win_rate": 62.0,
            "profit_factor": 1.6,
            "n_trades": 8,
        }),
    }

    df = _backtest_review_table(results)

    assert list(df["TF"]) == ["1M", "1W"]
    assert df.iloc[0]["Verdict"] == "Ưu tiên review"
    assert df.iloc[0]["Rank"] == 1


def test_backtest_review_summary_points_to_best_timeframe():
    compare_df = _backtest_review_table({
        "1M": _result({
            "cagr": 18.0,
            "total_return": 25.0,
            "sharpe": 1.5,
            "max_dd": -8.0,
            "win_rate": 62.0,
            "profit_factor": 1.6,
            "n_trades": 8,
        }),
        "3M": _result({
            "cagr": 4.0,
            "total_return": 2.0,
            "sharpe": 0.3,
            "max_dd": -18.0,
            "win_rate": 51.0,
            "profit_factor": 1.0,
            "n_trades": 2,
        }),
    })

    summary = _backtest_review_summary(compare_df)

    assert summary["best_tf"] == "1M"
    assert summary["robust_count"] == 1
    assert str(summary["next_action"]).startswith("Review sâu")


def test_backtest_review_table_handles_error_rows():
    df = _backtest_review_table({
        "5M": _result({"error": "Insufficient data"}),
    })

    assert df.iloc[0]["Verdict"] == "Thiếu dữ liệu"
    assert df.iloc[0]["Review Score"] == -1