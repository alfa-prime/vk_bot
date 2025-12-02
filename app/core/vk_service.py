import asyncio
import re
import vk_api
from vk_api.upload import VkUpload
from vk_api.exceptions import ApiHttpError, ApiError
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from app.core.config import get_settings


class VKService:
    """
    Сервис для работы с API ВКонтакте.
    Реализует Singleton для сессии и авторизации.
    """
    _session = None
    _api = None

    @classmethod
    def start(cls):
        """Инициализация и авторизация в ВК."""
        if cls._api is None:
            try:
                settings = get_settings()
                logger.info("VKService: Инициализация сессии...")

                # Авторизация по токену
                cls._session = vk_api.VkApi(token=settings.VK_TOKEN.get_secret_value())
                cls._api = cls._session.get_api()

                logger.info("VKService: Успешно.")
            except Exception as e:
                logger.critical(f"VKService Error: {e}")
                raise e

    @staticmethod
    def parse_link(link: str) -> tuple[int | None, str | None]:
        """Парсит ссылку вида vk.com/album-123_456 -> (-123, 456)."""
        match = re.search(r'album(-?\d+)_(\d+)', link)
        if match:
            return int(match.group(1)), match.group(2)
        return None, None

    # --- МЕТОДЫ ПОЛУЧЕНИЯ ФОТО ---

    @classmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((ApiHttpError, ConnectionError, TimeoutError)),
        reraise=True
    )
    def _get_photos_sync(cls, owner_id: int, album_id: str) -> list[str]:
        """Синхронный (блокирующий) запрос списка фото."""
        if cls._api is None:
            raise RuntimeError("VKService не запущен!")

        logger.debug(f"Запрос фото из альбома: {owner_id}_{album_id}")
        urls = []
        offset = 0
        count = 1000

        while True:
            response = cls._api.photos.get(
                owner_id=owner_id,
                album_id=album_id,
                photo_sizes=1,
                offset=offset,
                count=count
            )
            items = response.get('items', [])
            if not items:
                break

            for item in items:
                best_size = max(item['sizes'], key=lambda x: x['height'] * x['width'])
                urls.append(best_size['url'])

            offset += count
            if offset >= response['count']:
                break
        return urls

    @classmethod
    async def get_photo_urls(cls, owner_id: int, album_id: str) -> list[str] | None:
        """Асинхронная обертка для получения ссылок."""
        try:
            return await asyncio.to_thread(cls._get_photos_sync, owner_id, album_id)
        except Exception as e:
            logger.error(f"VKService Get Error: {e}")
            return None

    # --- МЕТОДЫ ЗАГРУЗКИ ФОТО ---

    @classmethod
    def _upload_sync(cls, file_obj, album_id: int, group_id: int = None):
        """Синхронная загрузка фото через VkUpload."""
        if cls._session is None:
            raise RuntimeError("VKService не запущен!")

        uploader = VkUpload(cls._session)
        return uploader.photo(
            photos=file_obj,
            album_id=album_id,
            group_id=group_id
        )

    @classmethod
    async def upload_photo(cls, file_obj, album_id: int, group_id: int = None):
        """Асинхронная обертка для загрузки фото."""
        try:
            return await asyncio.to_thread(cls._upload_sync, file_obj, album_id, group_id)
        except Exception as e:
            logger.error(f"VKService Upload Error: {e}")
            return None