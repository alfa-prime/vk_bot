import asyncio
import io
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import InputMediaPhoto, BufferedInputFile
from loguru import logger

from app.core.config import get_settings
from app.core.vk_service import VKService
from app.core.http_client import download_file

router = Router()


# --- СКАЧИВАНИЕ ИЗ ВКОНТАКТЕ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>VK Helper Bot</b>\n\n"
        "📥 <b>Скачать альбом:</b>\n"
        "`/get_album https://vk.com/album-123_456`\n\n"
        "📤 <b>Загрузить в альбом:</b>\n"
        "Просто отправь мне фото (или несколько) как картинки.",
        parse_mode="HTML"
    )


@router.message(Command("get_album"))
async def cmd_get_album(message: types.Message, command: CommandObject):
    """Команда для скачивания альбома из ВК в Телеграм."""
    if not command.args:
        await message.answer("⚠️ Укажите ссылку.")
        return

    # 1. Парсинг
    owner_id, album_id = VKService.parse_link(command.args.strip())
    if not owner_id:
        await message.answer("❌ Ссылка не распознана.")
        return

    msg = await message.answer("⏳ Получение списка фото...")

    # 2. Ссылки из ВК
    urls = await VKService.get_photo_urls(owner_id, album_id)
    if not urls:
        await msg.edit_text("❌ Альбом пуст или нет доступа.")
        return

    await msg.edit_text(f"✅ Найдено {len(urls)} фото. Отправляю...")
    logger.info(f"User {message.from_user.id} -> Download {len(urls)} photos")

    # 3. Скачивание и отправка
    media_group = []
    for i, url in enumerate(urls):
        try:
            data = await download_file(url)

            # Подготовка файла в памяти
            f = io.BytesIO(data)
            media = InputMediaPhoto(
                media=BufferedInputFile(f.getvalue(), filename=f"p_{i}.jpg")
            )
            media_group.append(media)

            if len(media_group) == 10:
                await message.answer_media_group(media=media_group)
                media_group = []
                await asyncio.sleep(1.0)  # Анти-флуд

        except Exception as e:
            logger.warning(f"Skip {url}: {e}")

    if media_group:
        await message.answer_media_group(media=media_group)

    await message.answer("🏁 Готово!")


# --- ЗАГРУЗКА В ВКОНТАКТЕ ---

@router.message(F.photo)
async def handle_upload(message: types.Message, bot: Bot):
    """
    Принимает фото от пользователя и грузит их в ВК.
    Срабатывает для каждого фото в альбоме.
    """
    settings = get_settings()

    # Проверка настроек
    if not settings.VK_UPLOAD_ALBUM_ID:
        await message.reply("⚙️ В настройках бота не задан ID альбома для загрузки.")
        return

    # Берем лучшее качество
    photo = message.photo[-1]

    try:
        # Скачиваем файл из Telegram
        file_io = io.BytesIO()
        await bot.download(photo.file_id, destination=file_io)
        file_io.seek(0)

        # Даем имя (VkUpload может требовать расширение)
        file_io.name = f"tg_{photo.file_id}.jpg"

        # Загружаем в ВК
        res = await VKService.upload_photo(
            file_io,
            settings.VK_UPLOAD_ALBUM_ID,
            settings.VK_UPLOAD_GROUP_ID
        )

        if res:
            # Ставим реакцию "класс", чтобы не спамить сообщениями
            # (Работает в новых версиях Aiogram и Telegram API)
            try:
                from aiogram.types import ReactionTypeEmoji
                await message.react([ReactionTypeEmoji(emoji="⚡")])
            except:
                await message.reply("✅")
        else:
            await message.reply("❌ Ошибка VK")

    except Exception as e:
        logger.error(f"Upload error: {e}")