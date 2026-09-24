import os
from pathlib import Path

def create_project_structure():
    print("🚀 Bootstrapping TradingOS Alpha v1.0...")

    # Define the directory structure based on the SRS
    directories = [
        ".github/workflows",
        "config",
        "data",
        "docs/proposal",
        "scripts",
        "src/tradingos/core",
        "src/tradingos/data",
        "src/tradingos/engines",
        "src/tradingos/ui/pages",
        "src/tradingos/ui/components",
        "src/tradingos/utils",
        "tests/integration",
        "tests/unit"
    ]

    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {dir_path}")

    # 1. requirements.txt
    requirements = """streamlit>=1.35.0
pandas>=2.0.0
numpy>=1.24.0
duckdb>=0.9.0
plotly>=5.20.0
requests>=2.31.0
pydantic>=2.0.0
hmmlearn>=0.3.0
scipy>=1.10.0
pytest>=7.0.0
flake8>=6.0.0
aiohttp>=3.8.0
"""
    with open("requirements.txt", "w") as f:
        f.write(requirements)

    # 2. config/default.toml
    default_toml = """[api]
ssi_base_url = "https://iboard-query.ssi.com.vn"
dnse_base_url = "https://services.entrade.com.vn"

[money_flow]
mcvd_lookback_days = 20
mcvd_slope_threshold = 0.01
sms_strong_buy = 70
"""
    with open("config/default.toml", "w") as f:
        f.write(default_toml)

    # 3. config/local.toml (Template for secrets)
    local_toml = """# DO NOT COMMIT THIS FILE
[secrets]
ssi_device_id = "YOUR_UUID_HERE"
telegram_bot_token = "YOUR_TOKEN_HERE"
"""
    with open("config/local.toml", "w") as f:
        f.write(local_toml)

    # 4. Streamlit Main App (src/tradingos/ui/app.py)
    app_py = """import streamlit as st

st.set_page_config(page_title="TradingOS Alpha", layout="wide", page_icon="📈")

st.sidebar.title("TradingOS Alpha v1.0")
st.sidebar.markdown("**Status:** HMM: `STEADY_BULL` | Ω: `0.55`")

pages = {
    "Analytics": [
        st.Page("pages/scanner.py", title="Market Scanner", icon="📡"),
        st.Page("pages/profiler.py", title="Stock Profiler", icon="🔍"),
        st.Page("pages/money_flow.py", title="Large Money Flow", icon="🐋"),
    ],
    "System": [
        st.Page("pages/backtest.py", title="Backtesting", icon="🧪"),
        st.Page("pages/audit.py", title="Audit Trail", icon="📜"),
        st.Page("pages/settings.py", title="Settings", icon="⚙️"),
    ]
}

pg = st.navigation(pages)
pg.run()
"""
    with open("src/tradingos/ui/app.py", "w", encoding="utf-8") as f:
        f.write(app_py)

    # 5. Create empty Streamlit pages to prevent errors
    pages = ["scanner.py", "profiler.py", "money_flow.py", "backtest.py", "audit.py", "settings.py"]
    for page in pages:
        with open(f"src/tradingos/ui/pages/{page}", "w", encoding="utf-8") as f:
            f.write(f"import streamlit as st\\n\\nst.title('{page.replace('.py', '').replace('_', ' ').title()}')\\nst.write('Under construction in Phase 3.')")

    # 6. .gitignore
    gitignore = """__pycache__/
*.pyc
.env
config/local.toml
data/*.duckdb
data/*.parquet
"""
    with open(".gitignore", "w") as f:
        f.write(gitignore)

    print("\\n🎉 TradingOS Alpha structure successfully generated!")
    print("Next steps:")
    print("1. pip install -r requirements.txt")
    print("2. streamlit run src/tradingos/ui/app.py")

if __name__ == "__main__":
    create_project_structure()