"""Browser E2E tests for the Streamlit UI."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest
import requests

playwright = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

from tradingos.data.cache import _DDL


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "src" / "tradingos" / "ui" / "app.py"


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, log_path: Path, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.ok:
                return
        except Exception as exc:  # pragma: no cover - exercised only while server boots
            last_error = str(exc)
        time.sleep(0.5)

    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    raise AssertionError(f"Streamlit server did not start in time. Last error: {last_error}\n{log_text}")


def _seed_test_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    con.execute(_DDL)

    now = datetime.now(timezone.utc)
    trade_day = date.today() - timedelta(days=1)
    older_trade_day = date.today() - timedelta(days=2)

    audit_payload_buy = json.dumps({
        "confidence": "HIGH",
        "signal_mode": "MODE_A",
        "tplus_verdict": "MUA_NGAY",
        "tplus_confidence": 82.0,
        "trend_warning": "UPTREND_STRENGTHENING",
        "fc_overall_vote": "TĂNG",
        "fc_overall_conf": 78.0,
        "mcvd_trend": "UP",
        "pt_net_5d": 1_250_000_000,
        "sector_flow": "INFLOW",
    })
    audit_payload_watch = json.dumps({
        "confidence": "MEDIUM",
        "signal_mode": "MODE_B",
        "tplus_verdict": "THEO_DOI",
        "tplus_confidence": 55.0,
        "trend_warning": "RANGE_COMPRESSION",
        "fc_overall_vote": "TRUNG LẬP",
        "fc_overall_conf": 51.0,
        "mcvd_trend": "FLAT",
        "pt_net_5d": 0,
        "sector_flow": "NEUTRAL",
    })

    con.execute("DELETE FROM audit_log")
    con.execute("DELETE FROM trade_ledger")

    con.execute(
        """INSERT INTO audit_log
           (audit_id,event_type,ticker,timestamp,signal_id,action,mfpm_score,sms_raw,amf_decision,rejected_reason,payload)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [
            "audit-buy", "PROFILE", "VCB", now - timedelta(hours=3), None, "BUY", 78, 68, "PASS", None, audit_payload_buy,
        ],
    )
    con.execute(
        """INSERT INTO audit_log
           (audit_id,event_type,ticker,timestamp,signal_id,action,mfpm_score,sms_raw,amf_decision,rejected_reason,payload)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [
            "audit-watch", "PROFILE", "SSI", now - timedelta(hours=2), None, "WATCH", 59, 52, "PASS", None, audit_payload_watch,
        ],
    )
    con.execute(
        """INSERT INTO trade_ledger
           (trade_id,ticker,entry_date,entry_price,initial_sl,signal_mode,mfpm_score,mc_prob,status,exit_date,exit_price,pnl_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            "trade-closed", "VCB", trade_day, 84500.0, 81200.0, "MODE_A", 78, 0.64, "CLOSED", date.today(), 90100.0, 6.63, now,
        ],
    )
    con.execute(
        """INSERT INTO trade_ledger
           (trade_id,ticker,entry_date,entry_price,initial_sl,signal_mode,mfpm_score,mc_prob,status,exit_date,exit_price,pnl_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            "trade-open", "SSI", older_trade_day, 31200.0, 29800.0, "MODE_B", 59, 0.52, "OPEN", None, None, None, now,
        ],
    )

    con.close()


@pytest.fixture(scope="module")
def live_streamlit_app(tmp_path_factory: pytest.TempPathFactory):
    db_dir = tmp_path_factory.mktemp("streamlit-e2e")
    db_path = db_dir / "e2e_ui.duckdb"
    log_path = db_dir / "streamlit.log"
    _seed_test_db(db_path)

    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["TRADINGOS_DB_PATH"] = str(db_path)

    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(APP_PATH),
                "--server.headless",
                "true",
                "--server.port",
                str(port),
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_for_server(base_url, log_path)
        yield {"url": base_url, "log_path": log_path}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - only hit on hung server
            proc.kill()


@pytest.fixture()
def browser_page(live_streamlit_app: dict):
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except PlaywrightError as exc:  # pragma: no cover - depends on local browser install
            pytest.skip(f"Chromium browser is not installed for Playwright: {exc}")

        page = browser.new_page()
        page.goto(live_streamlit_app["url"], wait_until="networkidle")
        expect(page.get_by_text("TradingOS α")).to_be_visible(timeout=15000)
        try:
            yield page
        finally:
            browser.close()


def _open_sidebar_page(page, label: str) -> None:
    sidebar = page.locator("[data-testid='stSidebar']")
    sidebar.get_by_text(label, exact=True).click()


def test_audit_page_e2e(browser_page) -> None:
    _open_sidebar_page(browser_page, "🗂 Audit")
    expect(browser_page.get_by_role("heading", name="🗂 Audit Log")).to_be_visible(timeout=10000)
    browser_page.get_by_role("button", name="🔍 Tìm kiếm").click()
    expect(browser_page.get_by_text("Cách đọc đúng theo hành vi thị trường Việt Nam")).to_be_visible()
    expect(browser_page.get_by_text("Sự kiện đang hiển thị", exact=False)).to_be_visible()
    expect(browser_page.get_by_text("sự kiện chi tiết", exact=False)).to_be_visible(timeout=10000)


def test_scanner_page_e2e(browser_page) -> None:
    _open_sidebar_page(browser_page, "📡 Scanner")
    expect(browser_page.get_by_role("heading", name="📡 Scanner")).to_be_visible(timeout=10000)
    expect(browser_page.get_by_text("Cách đọc kết quả Scanner")).to_be_visible()
    browser_page.get_by_label("Danh sách mã (mỗi mã một dòng, hoặc CSV — để trống = quét theo sàn đã chọn)").fill("VCB\nSSI")
    expect(browser_page.get_by_text("Hiển thị mã bị AMF chặn")).to_be_visible()
    browser_page.locator("[data-baseweb='select']").first.click()
    expect(browser_page.get_by_text("UPCOM", exact=True)).to_be_visible(timeout=10000)
    browser_page.keyboard.press("Escape")
    expect(browser_page.get_by_text("Hiển thị mã bị AMF chặn")).to_be_visible()


def test_performance_page_e2e(browser_page) -> None:
    _open_sidebar_page(browser_page, "🏆 Performance")
    expect(browser_page.get_by_role("heading", name="🏆 Hiệu suất Giao dịch (Paper Trading)")).to_be_visible(timeout=10000)
    expect(browser_page.get_by_text("Cách đọc trang Hiệu suất")).to_be_visible()
    expect(browser_page.get_by_text("Lệnh đang hiển thị", exact=False)).to_be_visible()
    expect(browser_page.get_by_text("Win rate trong view", exact=False)).to_be_visible()
    expect(browser_page.get_by_text("Chưa có giao dịch nào", exact=False)).to_have_count(0)