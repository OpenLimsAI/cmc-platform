from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='OPS_', env_file=ROOT / 'backend/.env', extra='ignore')
    mode: Literal['production', 'demo'] = 'production'
    component: Literal['api', 'collector', 'reader'] = 'api'
    jwt_algorithm: Literal['HS256', 'RS256'] = 'HS256'
    jwt_verify_key: SecretStr | None = None
    database_url: SecretStr | None = None
    rd_read_url: SecretStr | None = None
    gmp_read_url: SecretStr | None = None
    inventory_path: Path = ROOT / 'config/tasks.json'
    socket_path: Path = Path('/run/cmc-platform-monitor/events.sock')
    audit_fallback_path: Path = Path('/var/log/cmc-platform-monitor/access.jsonl')
    cron_schedule_path: Path = Path('/var/lib/cmc-platform-monitor/schedule-source/crontab.json')
    journal_socket_path: Path | None = None
    mdm_verification_path: Path = Path('/var/lib/cmc-platform-monitor/mdm-verification')
    source_timeout: float = Field(5, ge=1, le=10)
    batch_timeout: float = Field(30, ge=5, le=60)
    history_days: int = Field(7, ge=1, le=31)
    coalesce_seconds: float = Field(2, ge=0, le=5)
    max_pages: int = Field(20, ge=1, le=100)

    @model_validator(mode='after')
    def fail_closed(self):
        if self.component=='api':
            key = self.jwt_verify_key.get_secret_value() if self.jwt_verify_key else ''
            if len(key) < 32 or 'CHANGE_ME' in key:
                raise ValueError('必须配置MDM验签密钥，不支持开放模式')
            if self.jwt_algorithm == 'RS256' and 'PUBLIC KEY' not in key:
                raise ValueError('RS256需配置MDM公钥')
        if self.mode == 'production' and self.component!='reader':
            if not self.database_url or not self.database_url.get_secret_value().startswith('postgresql+asyncpg://'):
                raise ValueError('生产监控存储须配置PostgreSQL asyncpg连接')
        return self
