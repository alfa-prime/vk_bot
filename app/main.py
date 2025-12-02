import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from loguru import logger

from app.core.config import get_settings
from app.core.http_client import HTTPClient
from app.core.vk_service import VKService
from app.middlewares.album_middleware import AlbumMiddleware
from app.handlers import common, vk_features



async def setup_bot_commands(bot: Bot):
    """
    Определяем команды, которые будут видны в кнопке 'Меню'.
    """
    commands = [
        BotCommand(command="get_album", description="📥 Скачать альбом"),
        BotCommand(command="add_life", description="🖼 Загрузить в 'Life is Life'"),
        BotCommand(command="wall_post", description="📝 Опубликовать пост"),
        BotCommand(command="cancel", description="❌ Отмена действия"),
        BotCommand(command="start", description="🔄 Перезапуск бота"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot):
    logger.info("🚀 Startup...")
    HTTPClient.get_client()
    VKService.start()


async def on_shutdown(bot: Bot):
    logger.info("🛑 Shutdown...")
    await HTTPClient.close()


async def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

    settings = get_settings()
    bot = Bot(token=settings.TG_TOKEN.get_secret_value())
    dp = Dispatcher()

    # Подключаем Middleware для обработки альбомов
    # Он будет склеивать группы фото в один список
    dp.message.middleware(AlbumMiddleware())

    # Подключаем роутеры
    dp.include_router(common.router)
    dp.include_router(vk_features.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
