# python:3.14-slim — glibc-образ: для scipy/numpy нужны manylinux-колёса
FROM python:3.14-slim

# libgomp1 — OpenMP-рантайм, без него scipy падает с ImportError: libgomp.so.1
# apt-кэш сразу чистим, чтобы не тащить лишние мегабайты в слой
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Небуферизованный вывод — логи видны сразу; не пишем .pyc в контейнер
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Сначала только зависимости: слой pip переиспользуется, пока requirements.txt не изменился
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Код копируем после установки зависимостей — правка кода не инвалидирует pip-слой
COPY . .

# Не работаем под root: отдельный непривилегированный пользователь
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# HEALTHCHECK без curl: в slim его нет, а urllib есть в стандартной библиотеке
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/variant').status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
