import asyncio
from typing import Any, Dict, Union
from aiogram import BaseMiddleware
from aiogram.types import Message

class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.5):
        self.latency = latency
        self.album_data = {}

    async def __call__(self, handler, event: Message, data: Dict[str, Any]) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        key = event.media_group_id

        if key not in self.album_data:
            self.album_data[key] = {
                "messages": [event],
                "event": asyncio.Event()
            }
            # Ждем немного, пока придут остальные фото
            await asyncio.sleep(self.latency)
            self.album_data[key]["event"].set()
        else:
            self.album_data[key]["messages"].append(event)
            # Ждем пока первый поток разблокируется
            await self.album_data[key]["event"].wait()
            # Для остальных сообщений группы мы не вызываем handler,
            # так как первый поток обработает весь список.
            return

        # Первый поток забирает список и очищает словарь
        if key in self.album_data:
            messages = self.album_data[key]["messages"]
            del self.album_data[key]
            # Кладем список сообщений в data, чтобы хендлер его увидел
            data["album"] = messages
            return await handler(event, data)