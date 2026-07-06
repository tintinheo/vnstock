from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    data_source_priority: str = "KBS,CafeF,Vietstock,FireAnt,DNSE"
    max_risk_per_trade: float = Field(default=0.02, gt=0, le=0.05)
    max_position_pct: float = Field(default=0.20, gt=0, le=1)
    max_sector_pct: float = Field(default=0.35, gt=0, le=1)
    enable_ml: bool = False
    enable_streamlit: bool = True
    request_timeout_seconds: int = Field(default=12, ge=3, le=60)
    cache_dir: Path = Path("data_cache")
    audit_dir: Path = Path("audit_logs")
    reports_dir: Path = Path("reports")

    @property
    def sources(self) -> list[str]:
        return [source.strip() for source in self.data_source_priority.split(",") if source.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

