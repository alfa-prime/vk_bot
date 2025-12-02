# Используем легкий образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /code

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости, не кешируя загруженные пакеты
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всю папку app внутрь контейнера
COPY app/ ./app/

# Добавляем текущую директорию в PYTHONPATH, чтобы Python видел пакет "app"
ENV PYTHONPATH=/code

# Запускаем модуль app.main
CMD ["python", "-m", "app.main"]