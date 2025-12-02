from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    TG_TOKEN: SecretStr
    VK_TOKEN: SecretStr

    # ID альбома для команды /add_life
    VK_LIFE_ALBUM_ID: Optional[int] = None
    VK_LIFE_GROUP_ID: Optional[int] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings() # noqa