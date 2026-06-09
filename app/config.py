from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "Polars OLAP Cube"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./data/metadata.db"
    data_dir: str = "./data"
    parquet_dir: str = "./data/parquet"

    cache_ttl_seconds: int = 300
    cache_max_size: int = 1000

    refresh_interval_minutes: int = 60
    enable_auto_refresh: bool = True

    log_level: str = "INFO"


settings = Settings()
