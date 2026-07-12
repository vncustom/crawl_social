from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    fb_page_access_token: str
    fb_graph_version: str = "v25.0"
    app_secret_key: str
    report_timezone: str = "Asia/Bangkok"
    default_page_id: str = "1125132200689307"
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
