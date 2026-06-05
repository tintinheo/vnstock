"""
VN-Swing Alpha — root package marker.

Entry points:
    streamlit run Quant_Profiler_ui.py   # port 8501 — modular profiler
    streamlit run quant_app.py           # port 8502 — full dashboard

Sub-packages:
    engines/     — barrel re-exports for all analysis engines
    config/      — configuration constants (qp_config)
    data_layer/  — DuckDB persistence (db_cache)
    tests/       — unit + integration tests
"""
