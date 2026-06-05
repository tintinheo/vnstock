"""Root conftest.py — adds src/ to sys.path for all tests."""
import sys
from pathlib import Path

# Allow `import tradingos` without installation
ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
