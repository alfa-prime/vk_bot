from aiogram.fsm.state import StatesGroup, State

class GetAlbumState(StatesGroup):
    waiting_for_link = State()

class AddLifeState(StatesGroup):
    waiting_for_photos = State()

class WallPostState(StatesGroup):
    waiting_for_content = State()