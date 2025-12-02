from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Хендлер команды /start"""
    await state.clear()  # Сбрасываем любые зависшие состояния

    await message.answer(
        "👋 <b>Привет! Я твой VK-помощник.</b>\n\n"
        "Воспользуйся кнопкой <b>Меню</b> слева от поля ввода, чтобы выбрать действие:\n\n"
        "🔹 <b>/get_album</b> — Скачать фото из альбома ВК\n"
        "🔹 <b>/add_life</b> — Загрузить фото в альбом Life is Life\n"
        "🔹 <b>/wall_post</b> — Опубликовать пост на стене",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
@router.message(F.text.lower() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Хендлер отмены действия"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return

    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=types.ReplyKeyboardRemove())