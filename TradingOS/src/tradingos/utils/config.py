"""Utility: config loader — reads default.toml + local.toml + strategy.yaml."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-reattr]

import yaml

_ROOT = Path(__file__).parent.parent.parent.parent  # repo root


def _find_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    p = Path(__file__).resolve()
    for _ in range(8):
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


ROOT = _find_root()
CONFIG_DIR = ROOT / "config"


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as fh:
        raw = fh.read()
    # Strip UTF-8 BOM if present
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return tomllib.loads(raw.decode("utf-8"))


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class _Config:
    """Singleton config object."""

    def __init__(self) -> None:
        base = _load_toml(CONFIG_DIR / "default.toml")
        local = _load_toml(CONFIG_DIR / "local.toml")
        self._cfg: dict = _deep_merge(base, local)

        # strategy.yaml
        sy = CONFIG_DIR / "strategy.yaml"
        if sy.exists():
            with open(sy, encoding="utf-8") as fh:
                self._strategy: dict = yaml.safe_load(fh) or {}
        else:
            self._strategy = {}

    def get(self, *keys: str, default: Any = None) -> Any:
        """Dot-path access: get('api', 'ssi_api_base')."""
        node: Any = self._cfg
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    def strategy(self, *keys: str, default: Any = None) -> Any:
        """Access strategy.yaml values."""
        node: Any = self._strategy
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    @property
    def db_path(self) -> Path:
        raw = os.environ.get("TRADINGOS_DB_PATH") or self.get("data", "db_path", default="data/vn_cache.duckdb")
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def ssi_base(self) -> str:
        return self.get("api", "ssi_api_base", default="https://iboard-api.ssi.com.vn")

    @property
    def dnse_base(self) -> str:
        return self.get("api", "dnse_api_base", default="https://api.dnse.com.vn/chart-api/v2")

    @property
    def ssi_device_id(self) -> str:
        return os.environ.get("SSI_DEVICE_ID") or self.get("api", "ssi_device_id", default="")

    @property
    def fiinquantx_username(self) -> str:
        return os.environ.get("FIINQUANTX_USERNAME") or self.get("api", "fiinquantx_username", default="")

    @property
    def fiinquantx_password(self) -> str:
        return os.environ.get("FIINQUANTX_PASSWORD") or self.get("api", "fiinquantx_password", default="")

    @property
    def dnse_api_key(self) -> str:
        return os.environ.get("DNSE_API_KEY") or self.get("api", "dnse_api_key", default="")


cfg = _Config()
