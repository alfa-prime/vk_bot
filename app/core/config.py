from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    """
    Конфигурация приложения.
    Валидирует наличие переменных окружения при старте.
    """
    TG_TOKEN: SecretStr
    VK_TOKEN: SecretStr

    # Поля для загрузки фото (опциональные)
    VK_UPLOAD_ALBUM_ID: Optional[int] = None
    VK_UPLOAD_GROUP_ID: Optional[int] = None

    # Настройки Pydantic для чтения .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )


@lru_cache
def get_settings() -> Settings:
    """
    Возвращает объект настроек (Singleton).
    Файл читается только 1 раз благодаря lru_cache.
    """
    return Settings() # noqa
