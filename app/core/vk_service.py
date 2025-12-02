import asyncio
import re
import vk_api
from vk_api.upload import VkUpload
from vk_api.exceptions import ApiHttpError, ApiError
from requests.exceptions import RequestException, ConnectionError, Timeout
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from app.core.config import get_settings

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
        if cls._api is None:
            try:
                settings = get_settings()
                logger.info("VKService: Инициализация...")
                cls._session = vk_api.VkApi(token=settings.VK_TOKEN.get_secret_value())
                cls._api = cls._session.get_api()
                cls._check_connection()
                logger.info("VKService: Готов.")
            except Exception as e:
                logger.critical(f"VKService Error: {e}")
                raise e

    @classmethod
    @retry(**RETRY_CONFIG)
    def _check_connection(cls):
        cls._api.users.get()

    @staticmethod
    def parse_link(link: str):
        match_tagged = re.search(r'tag(\d+)', link)
        if match_tagged:
            return int(match_tagged.group(1)), 'tagged'

        match_album = re.search(r'album(-?\d+)_(\d+)', link)
        if match_album:
            owner_id = int(match_album.group(1))
            album_str = match_album.group(2)
            if album_str == '0':
                return owner_id, 'profile'
            elif album_str == '00':
                return owner_id, 'wall'
            elif album_str == '000':
                return owner_id, 'saved'
            else:
                return owner_id, album_str
        return None, None

    # --- НОВЫЙ МЕТОД ВЫБОРА РАЗМЕРА ---
    @staticmethod
    def _get_best_size(sizes: list) -> str:
        """
        Выбирает ссылку на фото максимального качества,
        опираясь на приоритеты типов размеров ВК.
        """
        if not sizes:
            return None

        # Приоритет типов (w - самый большой, s - самый маленький)
        # См. док: https://dev.vk.com/ru/reference/objects/photo-sizes
        type_priority = {
            'w': 10,  # Около 2560px
            'z': 9,  # 1080x1024
            'y': 8,  # 807x807
            'x': 7,  # 604x604
            'm': 6,  # 130x87
            's': 5,  # 75x55
            # Остальные (редкие типы)
            'o': 4, 'p': 3, 'q': 2, 'r': 1
        }

        # Сортируем список:
        # 1. Сначала по приоритету типа (если есть 'w', он победит)
        # 2. Если типы одинаковые или неизвестные, то по площади (ширина * высота)
        sizes.sort(key=lambda x: (
            type_priority.get(x.get('type'), 0),
            x.get('width', 0) * x.get('height', 0)
        ), reverse=True)

        return sizes[0]['url']

    # --- СКАЧИВАНИЕ ---
    @classmethod
    @retry(**RETRY_CONFIG)
    def _get_photos_sync(cls, owner_id: int, album_id: str):
        if cls._api is None: raise RuntimeError("VKService not started")

        urls = []
        offset = 0
        count = 1000

        while True:
            if album_id == 'tagged':
                response = cls._api.photos.getUserPhotos(
                    user_id=owner_id, sort='date', count=count, offset=offset, photo_sizes=1
                )
            else:
                response = cls._api.photos.get(
                    owner_id=owner_id, album_id=album_id, photo_sizes=1, offset=offset, count=count
                )

            items = response.get('items', [])
            if not items: break

            for item in items:
                if 'sizes' in item:
                    # Используем новый метод выбора
                    best_url = cls._get_best_size(item['sizes'])
                    if best_url:
                        urls.append(best_url)

            offset += count
            if offset >= response['count']: break

        return urls

    @classmethod
    async def get_photo_urls(cls, owner_id: int, album_id: str):
        try:
            return await asyncio.to_thread(cls._get_photos_sync, owner_id, album_id)
        except Exception as e:
            logger.error(f"Get photos error: {e}")
            return None

    # --- ЗАГРУЗКА И ПОСТИНГ (ОСТАЮТСЯ КАК БЫЛИ) ---
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
            logger.error(f"Error uploading: {e}")
            raise e

    @classmethod
    @retry(**RETRY_CONFIG)
    def _upload_wall_sync(cls, file_objs: list, group_id: int = None):
        for f in file_objs:
            if hasattr(f, 'seek'): f.seek(0)
        upload = VkUpload(cls._session)
        photos = upload.photo_wall(photos=file_objs, group_id=group_id)
        return ",".join([f"photo{p['owner_id']}_{p['id']}" for p in photos])

    @classmethod
    async def upload_wall_photos(cls, file_objs: list, group_id: int = None):
        return await asyncio.to_thread(cls._upload_wall_sync, file_objs, group_id)

    @classmethod
    @retry(**RETRY_CONFIG)
    def _post_wall_sync(cls, message: str, attachments: str, owner_id: int = None, from_group: bool = False):
        params = {
            "message": message, "attachments": attachments,
            "dont_parse_links": 1, "primary_attachments_mode": "grid"
        }
        if owner_id: params["owner_id"] = owner_id
        if from_group: params["from_group"] = 1
        return cls._api.wall.post(**params)

    @classmethod
    async def post_to_wall(cls, message: str = "", attachments: str = None, owner_id: int = None,
                           from_group: bool = False):
        return await asyncio.to_thread(cls._post_wall_sync, message, attachments, owner_id, from_group)