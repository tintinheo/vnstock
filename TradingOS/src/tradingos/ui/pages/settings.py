"""Settings page — config review + watchlist management."""
from __future__ import annotations

import streamlit as st

from tradingos.utils.config import cfg
from tradingos.data.cache import cache
from tradingos.engines.notification_service import notification_svc


def render() -> None:
    st.title("⚙️ Cài đặt")

    tab1, tab2, tab3, tab_api, tab_strat = st.tabs(
        ["📋 Config", "📌 Watchlist", "🗄 Database", "🔌 API Health", "🎛 Chiến lược"]
    )

    # ── Tab 1: Config viewer ──────────────────────────────────────────────
    with tab1:
        st.subheader("strategy.yaml snapshot")
        strategy = cfg.strategy()
        if isinstance(strategy, dict):
            for section, values in strategy.items():
                with st.expander(f"[{section}]"):
                    st.json(values)
        else:
            st.code(str(strategy))

        st.subheader("default.toml")
        st.markdown(f"- DB Path: `{cfg.db_path}`")
        st.markdown(f"- Log level: `{cfg.get('logging', 'level', default='INFO')}`")

    # ── Tab 2: Watchlist manager ──────────────────────────────────────────
    with tab2:
        current = cache.get_watchlist()
        st.markdown(f"**Watchlist hiện tại ({len(current)} mã):**")
        st.write(", ".join(current) if current else "_Chưa có mã nào._")

        with st.form("add_watchlist"):
            new_ticker = st.text_input("Thêm mã:", max_chars=10).upper()
            add = st.form_submit_button("➕ Thêm")
            if add and new_ticker:
                cache.add_to_watchlist(new_ticker)
                st.success(f"Đã thêm {new_ticker}")
                st.rerun()

        st.divider()
        st.markdown("**📥 Import nhiều mã (mỗi mã một dòng hoặc cách nhau dấu phẩy):**")
        bulk_text = st.text_area(
            "Dán danh sách mã:", height=120,
            placeholder="VCB\nTCB\nACB\nhoặc VCB,TCB,ACB",
            key="watchlist_bulk_import",
        )
        if st.button("💾 Import", key="bulk_import_btn"):
            raw = bulk_text.replace(",", "\n").replace(";", "\n")
            tickers = [t.strip().upper() for t in raw.splitlines() if t.strip()]
            added = 0
            for t in tickers:
                if t and t not in current:
                    cache.add_to_watchlist(t)
                    added += 1
            if added:
                st.success(f"✅ Đã thêm {added} mã mới vào watchlist.")
                st.rerun()
            else:
                st.info("Tất cả mã đã có trong watchlist.")

    # ── Tab 3: DB info ────────────────────────────────────────────────────
    with tab3:
        st.markdown(f"**DuckDB path:** `{cfg.db_path}`")
        try:
            import duckdb
            con = duckdb.connect(str(cfg.db_path), read_only=True)
            tables = con.execute("SHOW TABLES").fetchall()
            st.markdown("**Tables:**")
            cols_t = st.columns(3)
            for i, (t,) in enumerate(tables):
                try:
                    cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
                    cols_t[i % 3].metric(t, f"{cnt:,} rows")
                except Exception:
                    cols_t[i % 3].markdown(f"- `{t}`")
            con.close()
        except Exception as e:
            st.error(f"DB error: {e}")

        st.divider()
        st.markdown("**🧹 Bảo trì dữ liệu:**")
        c1, c2 = st.columns(2)
        if c1.button("🗑 Xóa scan_results cũ (>30 ngày)", key="purge_scan"):
            try:
                cache.purge_old_scan_results(days=30)
                st.success("Đã xóa scan results cũ.")
            except AttributeError:
                st.warning("Phương thức purge_old_scan_results chưa được implement.")
        if c2.button("📊 Vacuum DB", key="vacuum_db"):
            try:
                import duckdb
                con2 = duckdb.connect(str(cfg.db_path))
                con2.execute("VACUUM")
                con2.close()
                st.success("DB đã được vacuum.")
            except Exception as e:
                st.error(f"Vacuum error: {e}")

    # ── Tab 4: API Health Check ──────────────────────────────────────────
    with tab_api:
        st.markdown("### 🔌 Kiểm tra kết nối API")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**SSI iBoard**")
            if st.button("🔍 Ping SSI", key="ping_ssi"):
                with st.spinner("Đang kiểm tra..."):
                    try:
                        from tradingos.data.ssi_client import SSIClient  # type: ignore
                        ok = SSIClient().ping()
                        if ok:
                            st.success("✅ SSI iBoard online")
                        else:
                            st.error("❌ SSI iBoard không phản hồi")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

            st.markdown("**DNSE (fallback)**")
            if st.button("🔍 Ping DNSE", key="ping_dnse"):
                with st.spinner("Đang kiểm tra..."):
                    try:
                        import urllib.request
                        urllib.request.urlopen("https://finfo-api.dnse.com.vn/v1/stocks/VCB/quote", timeout=5)
                        st.success("✅ DNSE API online")
                    except Exception as e:
                        st.error(f"DNSE không khả dụng: {e}")

        with col_b:
            st.markdown("**Telegram Notification**")
            if st.button("🔔 Test Telegram", key="test_telegram"):
                with st.spinner("Gửi tin nhắn test..."):
                    ok, msg = notification_svc.test_connection()
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

            st.markdown("**Thông tin config Telegram:**")
            token_set = bool(cfg.get("notification", "telegram_bot_token", default=""))
            chat_set  = bool(cfg.get("notification", "telegram_chat_id", default=""))
            st.markdown(f"- Bot token: {'✅ đã set' if token_set else '❌ chưa set'}")
            st.markdown(f"- Chat ID: {'✅ đã set' if chat_set else '❌ chưa set'}")
            st.caption("Cấu hình tại `config/local.toml` → `[notification]`")

    # ── Tab 5: Strategy quick-edit ────────────────────────────────────────
    with tab_strat:
        st.markdown("### 🎛 Điều chỉnh tham số chiến lược nhanh")
        st.caption(
            "Thay đổi ở đây chỉ ảnh hưởng đến phiên hiện tại và lưu vào `config/local.toml`. "
            "Khởi động lại app để áp dụng."
        )

        strategy = cfg.strategy() or {}
        entry_cfg = strategy.get("entry", {})
        risk_cfg  = strategy.get("risk", {})

        with st.form("strat_form"):
            st.markdown("**Ngưỡng tín hiệu:**")
            sc1, sc2 = st.columns(2)
            mfpm_thresh = sc1.slider(
                "MFPM min (BUY)", 0, 120,
                int(entry_cfg.get("mfpm_threshold_buy", 60)), 5,
            )
            sms_thresh = sc2.slider(
                "SMS min (BUY)", 0, 100,
                int(entry_cfg.get("sms_threshold_buy", 50)), 5,
            )
            st.markdown("**Risk Management:**")
            rc1, rc2 = st.columns(2)
            kelly_pct = rc1.slider(
                "Kelly % max", 1, 30,
                int(risk_cfg.get("kelly_pct_max", 10)), 1,
            )
            atr_mult = rc2.slider(
                "ATR SL multiplier", 1.0, 4.0,
                float(risk_cfg.get("atr_sl_mult", 2.0)), 0.25,
            )
            save_btn = st.form_submit_button("💾 Lưu vào local.toml", type="primary")

        if save_btn:
            try:
                _save_strategy_overrides(mfpm_thresh, sms_thresh, kelly_pct, atr_mult)
                st.success("✅ Đã lưu. Khởi động lại Streamlit để áp dụng hoàn toàn.")
            except Exception as e:
                st.error(f"Lỗi khi lưu: {e}")


def _save_strategy_overrides(mfpm: int, sms: int, kelly: int, atr: float) -> None:
    """Append/update override section in config/local.toml."""
    import tomllib
    import tomli_w  # type: ignore[import]
    from pathlib import Path
    local_path = Path(cfg.db_path).parents[1] / "config" / "local.toml"
    data: dict = {}
    if local_path.exists():
        with open(local_path, "rb") as f:
            data = tomllib.load(f)
    data.setdefault("strategy_overrides", {})
    data["strategy_overrides"]["mfpm_threshold_buy"] = mfpm
    data["strategy_overrides"]["sms_threshold_buy"]  = sms
    data["strategy_overrides"]["kelly_pct_max"]       = kelly
    data["strategy_overrides"]["atr_sl_mult"]         = atr
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        tomli_w.dump(data, f)

