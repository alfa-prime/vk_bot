import asyncio
import io
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto, BufferedInputFile
from loguru import logger

from app.core.config import get_settings
from app.core.vk_service import VKService
from app.core.http_client import download_file
from app.states import GetAlbumState, AddLifeState, WallPostState

router = Router()


# ==========================================
# 1. СЦЕНАРИЙ: /get_album
# ==========================================

@router.message(Command("get_album"))
async def start_get_album(message: types.Message, state: FSMContext):
    await message.answer("🔗 Пришлите ссылку на альбом ВКонтакте.")
    await state.set_state(GetAlbumState.waiting_for_link)


@router.message(GetAlbumState.waiting_for_link, F.text)
async def process_get_album(message: types.Message, state: FSMContext):
    link = message.text.strip()
    owner_id, album_id = VKService.parse_link(link)

    if not owner_id:
        await message.answer("❌ Некорректная ссылка. Попробуйте еще раз или /cancel")
        return

    await message.answer("⏳ Сканирую альбом...")
    urls = await VKService.get_photo_urls(owner_id, album_id)

    if not urls:
        await message.answer("Альбом пуст или закрыт.")
        await state.clear()
        return

    await message.answer(f"Найдено {len(urls)} фото. Начинаю отправку...")

    # Логика отправки (пачками)
    media_group = []
    for i, url in enumerate(urls):
        try:
            data = await download_file(url)
            f = io.BytesIO(data)
            media = InputMediaPhoto(media=BufferedInputFile(f.getvalue(), filename=f"p_{i}.jpg"))
            media_group.append(media)

            if len(media_group) == 10:
                await message.answer_media_group(media=media_group)
                media_group = []
                await asyncio.sleep(1)
        except Exception:
            pass

    if media_group:
        await message.answer_media_group(media=media_group)

    await message.answer("✅ Готово!")
    await state.clear()


# ==========================================
# 2. СЦЕНАРИЙ: /add_life
# ==========================================

@router.message(Command("add_life"))
async def start_add_life(message: types.Message, state: FSMContext):
    settings = get_settings()
    if not settings.VK_LIFE_ALBUM_ID:
        await message.answer("⚙️ ID альбома не настроен в .env")
        return

    await message.answer(
        "🖼 <b>Режим Life is Life</b>\n"
        "Пришлите одну или несколько фотографий, и я загружу их в альбом.",
        parse_mode="HTML"
    )
    await state.set_state(AddLifeState.waiting_for_photos)


@router.message(AddLifeState.waiting_for_photos, F.photo)
async def process_add_life(message: types.Message, state: FSMContext, bot: Bot, album: list[types.Message] = None):
    settings = get_settings()

    # Если это группа фото (альбом), берем список из middleware, иначе список из одного сообщения
    messages = album if album else [message]

    await message.answer("⏳ Загружаю в ВК...")

    file_streams = []
    try:
        for msg in messages:
            # Берем лучшее качество
            file_id = msg.photo[-1].file_id
            f = io.BytesIO()
            await bot.download(file_id, destination=f)
            f.seek(0)
            f.name = f"img_{file_id}.jpg"  # Важно для vk_api
            file_streams.append(f)

        await VKService.upload_photos_to_album(
            file_streams,
            album_id=settings.VK_LIFE_ALBUM_ID,
            group_id=settings.VK_LIFE_GROUP_ID
        )
        await message.answer(f"✅ Успешно загружено {len(messages)} фото в альбом Life is Life!")

    except Exception as e:
        logger.error(e)
        await message.answer("❌ Ошибка при загрузке.")

    await state.clear()


# ==========================================
# 3. СЦЕНАРИЙ: /wall_post
# ==========================================

@router.message(Command("wall_post"))
async def start_wall_post(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 <b>Постинг на стену</b>\n"
        "Пришлите текст, фото (можно с подписью) или видео.\n"
        "Если пришлете несколько фото, они будут сеткой.",
        parse_mode="HTML"
    )
    await state.set_state(WallPostState.waiting_for_content)


@router.message(WallPostState.waiting_for_content)
async def process_wall_post(message: types.Message, state: FSMContext, bot: Bot, album: list[types.Message] = None):
    text_content = message.text or message.caption or ""

    # Если просто текст
    if not message.photo and not message.video and message.text:
        await VKService.post_to_wall(message=text_content)
        await message.answer("✅ Текстовый пост опубликован.")
        await state.clear()
        return

    # Если фото (одно или альбом)
    if message.photo:
        messages = album if album else [message]
        msg_wait = await message.answer(f"⏳ Обработка {len(messages)} фото...")

        file_streams = []
        # Если подпись была у первого фото в альбоме
        caption = messages[0].caption or ""

        try:
            for msg in messages:
                f = io.BytesIO()
                await bot.download(msg.photo[-1].file_id, destination=f)
                f.seek(0)
                f.name = f"wall_{msg.message_id}.jpg"
                file_streams.append(f)

            # 1. Загружаем фото на сервер ВК
            attachments_str = await VKService.upload_wall_photos(file_streams)

            # 2. Публикуем пост
            await VKService.post_to_wall(message=caption, attachments=attachments_str)
            await msg_wait.edit_text("✅ Пост с фото опубликован!")

        except Exception as e:
            logger.error(f"Wall post error: {e}")
            await msg_wait.edit_text("❌ Ошибка публикации.")

        await state.clear()
        return

    # Если видео (пока простая реализация, видео требует сложной загрузки)
    if message.video:
        await message.answer("⚠️ Загрузка видео пока в разработке (требует сложного API ВК). Пришлите ссылку или фото.")
        return