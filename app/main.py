import asyncio
import sys
from aiogram import Bot, Dispatcher
from loguru import logger

from app.core.config import get_settings
from app.core.http_client import HTTPClient
from app.core.vk_service import VKService
from app.handlers import album


async def on_startup(bot: Bot):
    """Хук при запуске: инициализация сервисов."""
    logger.info("🚀 Startup...")
    HTTPClient.get_client()  # Прогрев HTTP
    VKService.start()  # Авторизация ВК


async def on_shutdown(bot: Bot):
    """Хук при остановке: очистка ресурсов."""
    logger.info("🛑 Shutdown...")
    await HTTPClient.close()


async def main():
    """Точка входа."""
    # Настройка логгера
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

    settings = get_settings()

    # Инициализация бота
    bot = Bot(token=settings.TG_TOKEN.get_secret_value())
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(album.router)

    # Регистрация событий
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запущен!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")