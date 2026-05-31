from __future__ import annotations

from ui.guide_tab import _guide_quickstart


def test_guide_quickstart_returns_four_vi_steps():
    steps = _guide_quickstart("VI")

    assert len(steps) == 4
    assert steps[0]["title"].startswith("1.")
    assert "Tải dữ liệu" in steps[0]["body"] or "Tải dữ liệu" in steps[0]["title"]


def test_guide_quickstart_returns_four_en_steps():
    steps = _guide_quickstart("EN")

    assert len(steps) == 4
    assert steps[1]["title"].startswith("2.")
    assert "refresh macro" in steps[1]["body"].lower()