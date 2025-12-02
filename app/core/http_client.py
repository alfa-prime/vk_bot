import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

class HTTPClient:
    """
    Глобальный HTTP-клиент (Singleton).
    Позволяет переиспользовать TCP-соединения для ускорения работы.
    """
    _client: httpx.AsyncClient = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Получить текущий экземпляр клиента или создать новый."""
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=30.0)
            logger.debug("HTTPClient: Создана новая сессия.")
        return cls._client

    @classmethod
    async def close(cls):
        """Закрыть сессию при остановке бота."""
        if cls._client:
            await cls._client.aclose()
            cls._client = None # noqa
            logger.info("HTTPClient: Сессия закрыта.")

@retry(
    stop=stop_after_attempt(3),      # Повторять 3 раза
    wait=wait_fixed(2),              # Ждать 2 секунды
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    reraise=True
)
async def download_file(url: str) -> bytes:
    """
    Скачивает файл по URL.
    При сбое сети автоматически делает повторные попытки.
    """
    client = HTTPClient.get_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.content