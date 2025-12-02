import asyncio
import re
import vk_api
from vk_api.upload import VkUpload
from vk_api.exceptions import ApiHttpError, ApiError, VkApiError
# Импортируем ошибки requests, так как vk_api использует их
from requests.exceptions import RequestException, ConnectionError, Timeout

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from app.core.config import get_settings

# Конфигурация для повторных попыток (Retries)
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_fixed(2),
    "retry": retry_if_exception_type((
        ApiHttpError, RequestException, ConnectionError, Timeout
    )),
    "reraise": True
}


class VKService:
    _session = None
    _api = None

    @classmethod
    def start(cls):
        """Авторизация и проверка соединения."""
        if cls._api is None:
            try:
                settings = get_settings()
                logger.info("VKService: Инициализация...")

                cls._session = vk_api.VkApi(token=settings.VK_TOKEN.get_secret_value())
                cls._api = cls._session.get_api()

                cls._check_connection()

                logger.info("VKService: Успешно подключено.")
            except Exception as e:
                logger.critical(f"VKService Critical Error: {e}")
                raise e

    @classmethod
    @retry(**RETRY_CONFIG)
    def _check_connection(cls):
        cls._api.users.get()

    @staticmethod
    def parse_link(link: str):
        match = re.search(r'album(-?\d+)_(\d+)', link)
        if match:
            return int(match.group(1)), match.group(2)
        return None, None

    # --- GET PHOTOS ---
    @classmethod
    @retry(**RETRY_CONFIG)
    def _get_photos_sync(cls, owner_id: int, album_id: str):
        if cls._api is None: raise RuntimeError("VKService not started")
        urls = []
        offset = 0
        count = 1000
        while True:
            response = cls._api.photos.get(
                owner_id=owner_id, album_id=album_id, photo_sizes=1, offset=offset, count=count
            )
            items = response.get('items', [])
            if not items: break
            for item in items:
                best_size = max(item['sizes'], key=lambda x: x['height'] * x['width'])
                urls.append(best_size['url'])
            offset += count
            if offset >= response['count']: break
        return urls

    @classmethod
    async def get_photo_urls(cls, owner_id: int, album_id: str):
        try:
            return await asyncio.to_thread(cls._get_photos_sync, owner_id, album_id)
        except Exception as e:
            logger.error(f"Error getting album: {e}")
            return None

    # --- UPLOAD TO ALBUM ---
    @classmethod
    @retry(**RETRY_CONFIG)
    def _upload_album_sync(cls, file_objs: list, album_id: int, group_id: int = None):
        for f in file_objs:
            if hasattr(f, 'seek'): f.seek(0)
        upload = VkUpload(cls._session)
        return upload.photo(photos=file_objs, album_id=album_id, group_id=group_id)

    @classmethod
    async def upload_photos_to_album(cls, file_objs: list, album_id: int, group_id: int = None):
        try:
            return await asyncio.to_thread(cls._upload_album_sync, file_objs, album_id, group_id)
        except Exception as e:
            logger.error(f"Error uploading to album: {e}")
            raise e

    # --- WALL POST ---
    @classmethod
    @retry(**RETRY_CONFIG)
    def _upload_wall_sync(cls, file_objs: list, group_id: int = None):
        for f in file_objs:
            if hasattr(f, 'seek'): f.seek(0)

        upload = VkUpload(cls._session)
        photos = upload.photo_wall(photos=file_objs, group_id=group_id)

        attachments = []
        for p in photos:
            attachments.append(f"photo{p['owner_id']}_{p['id']}")
        return ",".join(attachments)

    @classmethod
    async def upload_wall_photos(cls, file_objs: list, group_id: int = None):
        return await asyncio.to_thread(cls._upload_wall_sync, file_objs, group_id)

    @classmethod
    @retry(**RETRY_CONFIG)
    def _post_wall_sync(cls, message: str, attachments: str, owner_id: int = None, from_group: bool = False):
        params = {
            "message": message,
            "attachments": attachments,
            "dont_parse_links": 1,  # Не делать ссылки-сниппеты
            "primary_attachments_mode": "grid"  # Принудительная сетка!
        }

        if owner_id:
            params["owner_id"] = owner_id
        if from_group:
            params["from_group"] = 1

        return cls._api.wall.post(**params)

    @classmethod
    async def post_to_wall(cls, message: str = "", attachments: str = None, owner_id: int = None,
                           from_group: bool = False):
        return await asyncio.to_thread(cls._post_wall_sync, message, attachments, owner_id, from_group)