from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    ADMIN_IDS: list[int]

    ADMIN_PANEL_URL: str
    ADMIN_PANEL_TOKEN: str
    ADMIN_PANEL_TOTP_SECRET: str | None = None
    AGENT_TOKEN: str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    SHARE_PROXY_ON_INVITE_ENABLED: bool = False
    VPN_ADS_ON_SHARE_LINK: str | None = None

    # True = webhook (production), False = polling (local development)
    WEBHOOK_MODE_ENABLED: bool = True

    WEBHOOK_BASE_URL: str = ""
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_SECRET: str = ""
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = 8080

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
