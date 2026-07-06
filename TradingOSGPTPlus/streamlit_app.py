"""Project entrypoint for Streamlit Community Cloud.

Deploy this file as the app path:
TradingOSGPTPlus/streamlit_app.py
"""

import runpy
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

runpy.run_module("app.ui.streamlit_app", run_name="__main__")
