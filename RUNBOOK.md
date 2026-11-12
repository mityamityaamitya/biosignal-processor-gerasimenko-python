# Руководство по запуску и тестированию

Практическое руководство к проекту **biosignal-processor-gerasimenko-python**
(вариант 4, ЭКГ). Здесь — все команды по порядку: от установки окружения до
приёмки в Docker, с ожидаемым выводом, контрольными числами и разбором типовых
ошибок. Математика и описание алгоритмов — в [README.md](README.md), здесь только
эксплуатация.

Оглавление:

1. [Что понадобится](#1-что-понадобится)
2. [Быстрый старт](#2-быстрый-старт)
3. [Шаг 1. Клонирование и виртуальное окружение](#3-шаг-1-клонирование-и-виртуальное-окружение)
4. [Шаг 2. Установка зависимостей](#4-шаг-2-установка-зависимостей)
5. [Шаг 3. Запуск сервера локально](#5-шаг-3-запуск-сервера-локально)
6. [Шаг 4. Проверка API вручную](#6-шаг-4-проверка-api-вручную)
7. [Шаг 5. Автоматическая сверка с эталоном](#7-шаг-5-автоматическая-сверка-с-эталоном)
8. [Шаг 6. Проверка ошибок](#8-шаг-6-проверка-ошибок)
9. [Шаг 7. Клиент с графиками](#9-шаг-7-клиент-с-графиками)
10. [Шаг 8. Синтетическая ЭКГ](#10-шаг-8-синтетическая-экг)
11. [Шаг 9. Запуск и проверка в Docker](#11-шаг-9-запуск-и-проверка-в-docker)
12. [Полный чек-лист приёмки](#12-полный-чек-лист-приёмки)
13. [Диагностика проблем](#13-диагностика-проблем)
14. [Что и где менять](#14-что-и-где-менять)
15. [Git-процесс](#15-git-процесс)
16. [Справочник API](#16-справочник-api)
17. [Ограничения](#17-ограничения)

---

## 1. Что понадобится

| Компонент | Версия | Зачем |
|---|---|---|
| Python | 3.14 (проверено на 3.14.5) | сервер и клиент |
| pip | 26.x | установка зависимостей в `venv` |
| Git | любая актуальная | ветка `dev`, история коммитов |
| Docker + Compose | Docker 29.x, Compose v5 (проверено на OrbStack) | запуск в контейнере |
| Свободный порт | `8000/tcp` | сервер и контейнер |

Проверка:

```bash
python3 --version
git --version
docker --version && docker compose version
```

> **Windows.** Все команды ниже выполняются в PowerShell или Git Bash.
> Активация окружения — `venv\Scripts\activate` (PowerShell:
> `venv\Scripts\Activate.ps1`). Docker-часть идентична.

> **Системный Python не трогаем.** На macOS/Homebrew и большинстве Linux установка
> пакетов в системный интерпретатор запрещена (PEP 668, ошибка
> `externally-managed-environment`). Только `venv`.

---

## 2. Быстрый старт

Если нужен результат «прямо сейчас», а не объяснения:

```bash
# 1. окружение и зависимости
cd biosignal-processor-gerasimenko-python
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 2. сервер (в отдельном терминале, окружение активировано)
uvicorn app:app --host 127.0.0.1 --port 8000

# 3. проверка
curl -s http://127.0.0.1:8000/variant
curl -F "file=@test_data/raw_signal.txt" "http://127.0.0.1:8000/analyze?fs=250"
python test_data/test_client.py

# 4. Docker (вместо шага 2, если нужен контейнер)
docker compose up --build -d
docker compose ps
docker compose down
```

Ожидаемый результат анализа: **6 событий**, `mean_qrs_width_ms ≈ 88.67`,
`max_peak_amplitude ≈ 0.9956`, `heart_rate_bpm ≈ 70.75`.

---

## 3. Шаг 1. Клонирование и виртуальное окружение

```bash
git clone <ссылка_на_репозиторий> biosignal-processor-gerasimenko-python
cd biosignal-processor-gerasimenko-python
git checkout dev
```

Создание и активация окружения:

```bash
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows (cmd)
# venv\Scripts\Activate.ps1       # Windows (PowerShell)
```

Признак активации — префикс `(venv)` в приглашении. Проверка, что `python` и `pip`
указывают внутрь окружения:

```bash
which python
which pip
python --version
```

Ожидается путь, содержащий `/venv/bin/python`, и Python 3.14.x.

---

## 4. Шаг 2. Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` — результат `pip freeze` рабочего окружения, все версии
зафиксированы (`fastapi==0.162.5`, `uvicorn[standard]==0.54.0`,
`numpy==2.5.4`, `scipy==1.18.1`, `matplotlib==3.10.8`, `requests==2.32.5`,
`python-multipart==0.0.33` и транзитивные).

Проверка импортов — **обязательный шаг**, дальше без неё нет смысла идти:

```bash
python -c "import numpy, scipy, fastapi, uvicorn, matplotlib, requests; print('ok', numpy.__version__, scipy.__version__)"
```

Ожидаемый вывод:

```
ok 2.5.4 1.18.1
```

Проверка, что ядро обработки импортируется без веб-фреймворка (принцип
«чистых функций»):

```bash
python -c "import signal_processor; print('ядро ok')"
```

---

## 5. Шаг 3. Запуск сервера локально

### Вариант A — uvicorn напрямую (рекомендуется для проверки)

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

### Вариант B — через точку входа

```bash
python app.py
```

`app.py` в режиме `__main__` вызывает `uvicorn.run(..., reload=True)`, поэтому
правки кода подхватываются без перезапуска.

### Вариант C — с автоперезагрузкой и логами запросов

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Признак успешного старта в логе:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Остановка — `Ctrl+C`. Если сервер запущен в фоне:

```bash
pkill -f "uvicorn app:app"
```

Проверка, что порт занят именно нашим процессом:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

---

## 6. Шаг 4. Проверка API вручную

Все команды выполняются из корня проекта, сервер слушает `127.0.0.1:8000`.

### 6.1 Параметры варианта

```bash
curl -s http://127.0.0.1:8000/variant
```

Ожидаемо (сокращённо): `"variant":"4"`, `"moving_average_window":7`,
`"highpass":{"order":2,"cutoff_hz":0.5}`, `"qrs_energy_threshold_ratio":0.1`,
`"default_fs":250.0`.

### 6.2 Swagger и OpenAPI

```bash
curl -s -o /dev/null -w "docs: %{http_code}\n"    http://127.0.0.1:8000/docs
curl -s -o /dev/null -w "openapi: %{http_code}\n" http://127.0.0.1:8000/openapi.json
curl -s http://127.0.0.1:8000/openapi.json | head -c 200
```

Ожидается `docs: 200`, `openapi: 200` и JSON, начинающийся с
`{"openapi":"3.1.0","info":{"title":"Universal Bio-Signal Processing Server"…`.

В браузере: <http://127.0.0.1:8000/docs> → `POST /analyze` → **Try it out** →
`fs = 250`, `column = 0`, файл `test_data/raw_signal.txt` → **Execute**.

### 6.3 Анализ реальной ЭКГ

```bash
curl -F "file=@test_data/raw_signal.txt" "http://127.0.0.1:8000/analyze?fs=250" -o /tmp/analyze.json
```

Краткий разбор ответа без `jq`:

```bash
python - <<'PY'
import json
data = json.load(open("/tmp/analyze.json"))
print("статус:", data["status"], "| отсчётов:", data["signal_length"], "| событий:", len(data["detected_events"]))
for event in data["detected_events"]:
    print(f'R={event["r_peak_index"]:>4}  onset={event["onset_index"]:>4}  offset={event["offset_index"]:>4}  ширина={event["width_ms"]:>5} мс')
print(json.dumps(data["calculated_features"], ensure_ascii=False, indent=2))
PY
```

Ожидаемый вывод:

```
статус: success | отсчётов: 1250 | событий: 6
R= 116  onset= 108  offset= 127  ширина= 76.0 мс
R= 325  onset= 317  offset= 339  ширина= 88.0 мс
R= 532  onset= 524  offset= 545  ширина= 84.0 мс
R= 742  onset= 734  offset= 755  ширина= 84.0 мс
R= 957  onset= 946  offset= 971  ширина=100.0 мс
R=1176  onset=1165  offset=1190  ширина=100.0 мс
{
  "mean_qrs_width_ms": 88.666667,
  "max_peak_amplitude": 0.995602,
  "mean_amplitude": 1.7e-05,
  "std_amplitude": 0.172234,
  "heart_rate_bpm": 70.754717,
  "r_peak_count": 6,
  "qrs_count": 6
}
```

### 6.4 Многоколоночный файл

Проверка параметра `column` — берём синтетику с колонкой времени:

```bash
python test_data/synthetic_ecg_generator.py --beats 4 --heart-rate 90 \
       --with-time-column --output /tmp/two_columns.txt
head -2 /tmp/two_columns.txt          # 0.0000 -0.001  → две колонки
curl -s -F "file=@/tmp/two_columns.txt" \
     "http://127.0.0.1:8000/analyze?fs=250&column=1"
```

Ожидается `"r_peak_count": 4` и `"heart_rate_bpm": 90.0`.

---

## 7. Шаг 5. Автоматическая сверка с эталоном

Скрипт ниже сам проверяет ответ API по допускам задания: ±2 отсчёта по границам,
±2 мс по средней ширине, ±0.01 по амплитудам, ±0.5 BPM по ЧСС. Код возврата
`0` — всё сошлось, `1` — есть расхождения (они печатаются).

```bash
python - <<'PY'
import sys
import requests

URL = "http://127.0.0.1:8000/analyze?fs=250"

with open("test_data/raw_signal.txt", "rb") as handle:
    response = requests.post(
        URL,
        files={"file": ("raw_signal.txt", handle, "text/plain")},
        timeout=60,
    )

if response.status_code != 200:
    print("HTTP", response.status_code, response.text)
    sys.exit(1)

data = response.json()
events = data["detected_events"]
features = data["calculated_features"]

expected_peaks = [116, 325, 532, 742, 957, 1176]
expected_bounds = [(108, 127), (317, 339), (524, 545), (734, 755), (946, 971), (1165, 1190)]
expected_widths = [76.0, 88.0, 84.0, 84.0, 100.0, 100.0]

problems = []

if data["status"] != "success":
    problems.append(f"status = {data['status']}")
if data["fs"] != 250.0:
    problems.append(f"fs = {data['fs']}")
if data["variant"] != "4":
    problems.append(f"variant = {data['variant']}")
if len(events) != 6:
    problems.append(f"событий {len(events)}, ожидалось 6")

peaks = [event["r_peak_index"] for event in events]
if peaks != expected_peaks:
    problems.append(f"R-пики {peaks} != {expected_peaks}")

for index, (event, bounds) in enumerate(zip(events, expected_bounds)):
    got = (event["onset_index"], event["offset_index"])
    if abs(got[0] - bounds[0]) > 2 or abs(got[1] - bounds[1]) > 2:
        problems.append(f"границы #{index + 1}: {got} != {bounds} (±2)")
    if abs(event["width_ms"] - expected_widths[index]) > 2.0:
        problems.append(f"ширина #{index + 1}: {event['width_ms']} != {expected_widths[index]} (±2 мс)")

tolerances = {
    "mean_qrs_width_ms": (88.67, 2.0),
    "max_peak_amplitude": (0.9958, 0.01),
    "std_amplitude": (0.1715, 0.01),
    "heart_rate_bpm": (70.75, 0.5),
}
for name, (expected, tolerance) in tolerances.items():
    value = features[name]
    if value is None or abs(value - expected) > tolerance:
        problems.append(f"{name} = {value}, ожидалось {expected} ±{tolerance}")

if problems:
    print("РАСХОЖДЕНИЯ:")
    for problem in problems:
        print(" -", problem)
    sys.exit(1)

print("OK: 6 событий, границы, ширины, ЧСС и амплитуды совпали с эталоном §3.2")
PY
```

Ожидаемый вывод: `OK: 6 событий, границы, ширины, ЧСС и амплитуды совпали с эталоном §3.2`.

> Скрипт удобно сохранить как `scripts/check_reference.py` и запускать в CI.
> Он использует только `requests`, который уже есть в `requirements.txt`.

---

## 8. Шаг 6. Проверка ошибок

Готовим «плохие» файлы:

```bash
mkdir -p /tmp/bsneg
cp test_data/raw_signal.txt /tmp/bsneg/signal.dat      # неверное расширение
: > /tmp/bsneg/empty.txt                               # пустой файл
printf 'не число\nещё строка\n' > /tmp/bsneg/text.txt  # текст вместо чисел
head -5 test_data/raw_signal.txt > /tmp/bsneg/short.txt # 5 отсчётов < 10
```

Прогон всех сценариев:

```bash
for file in signal.dat empty.txt text.txt short.txt; do
  echo "== $file"
  curl -s -F "file=@/tmp/bsneg/$file" "http://127.0.0.1:8000/analyze?fs=250" -w " [HTTP %{http_code}]\n"
done

echo "== fs=0"
curl -s -F "file=@test_data/raw_signal.txt" "http://127.0.0.1:8000/analyze?fs=0" -w " [HTTP %{http_code}]\n"

echo "== column=5"
curl -s -F "file=@test_data/raw_signal.txt" "http://127.0.0.1:8000/analyze?fs=250&column=5" -w " [HTTP %{http_code}]\n"
```

Ожидаемая таблица:

| Сценарий | HTTP | `error` |
|---|---|---|
| `signal.dat` | 400 | `INVALID_FILE_FORMAT` |
| `empty.txt` | 400 | `EMPTY_FILE` |
| `text.txt` | 400 | `PARSE_ERROR` |
| `short.txt` (5 отсчётов) | 400 | `SIGNAL_TOO_SHORT` |
| `fs=0` | 400 | `INVALID_SAMPLING_RATE` |
| `column=5` при одной колонке | 400 | `INVALID_COLUMN` |

Формат тела ошибки одинаковый:

```json
{"error": "КОД", "errorDetails": {"code": "КОД", "details": "текст"}}
```

Автоматическая проверка кодов:

```bash
python - <<'PY'
import requests

cases = [
    ("test_data/raw_signal.txt", "signal.dat", {}, 400, "INVALID_FILE_FORMAT"),
    ("/tmp/bsneg/empty.txt", "empty.txt", {}, 400, "EMPTY_FILE"),
    ("/tmp/bsneg/text.txt", "text.txt", {}, 400, "PARSE_ERROR"),
    ("/tmp/bsneg/short.txt", "short.txt", {}, 400, "SIGNAL_TOO_SHORT"),
    ("test_data/raw_signal.txt", "raw_signal.txt", {"fs": 0}, 400, "INVALID_SAMPLING_RATE"),
    ("test_data/raw_signal.txt", "raw_signal.txt", {"column": 5}, 400, "INVALID_COLUMN"),
]

for path, name, params, status, code in cases:
    with open(path, "rb") as handle:
        response = requests.post(
            "http://127.0.0.1:8000/analyze",
            files={"file": (name, handle, "text/plain")},
            params=params,
            timeout=60,
        )
    body = response.json()
    ok = response.status_code == status and body.get("error") == code
    print(("OK  " if ok else "FAIL"), name, params, "->", response.status_code, body.get("error"))
PY
```

---

## 9. Шаг 7. Клиент с графиками

```bash
python test_data/test_client.py
```

Что делает скрипт:

1. отправляет `test_data/raw_signal.txt` на `POST /analyze`;
2. печатает параметры записи, таблицу признаков и первые 10 событий;
3. сохраняет два PNG в `test_data/plots/`.

Ожидаемый вывод (сокращённо):

```
Параметры обработки
---------------------------------------------------------------
Файл                   …/test_data/raw_signal.txt
Сервер                 http://127.0.0.1:8000
Вариант                4
Частота дискретизации  250 Гц
Колонка                0
Отсчётов               1250
Длительность записи    5.000 с
Событий (QRS)          6

Рассчитанные признаки
------------------------------------------
mean_qrs_width_ms   88.666667 мс
max_peak_amplitude  0.995602
mean_amplitude      1.7e-05
std_amplitude       0.172234
heart_rate_bpm      70.754717 BPM
r_peak_count        6
qrs_count           6
…
Графики сохранены:
  …/test_data/plots/raw_signal.png
  …/test_data/plots/filtered_signal.png
```

Опции:

| Опция | По умолчанию | Назначение |
|---|---|---|
| `--url` | `http://127.0.0.1:8000` | адрес сервера |
| `--file` | `test_data/raw_signal.txt` | файл сигнала |
| `--fs` | `250` | частота дискретизации |
| `--column` | `0` | индекс колонки |
| `--no-plots` | выкл. | только признаки, без PNG |
| `--output-dir` | `test_data/plots` | куда сохранять графики |

Примеры:

```bash
python test_data/test_client.py --no-plots
python test_data/test_client.py --file test_data/synthetic_signal.txt --no-plots
python test_data/test_client.py --output-dir /tmp/plots --fs 250 --column 0
cd test_data && ../venv/bin/python test_client.py        # запуск из подкаталога
```

Графики:

- `raw_signal.png` — исходный сигнал, X «Время, с», Y «Амплитуда»;
- `filtered_signal.png` — отфильтрованный сигнал, закрашенные зоны `onset–offset`
  и красные метки R-пиков.

Коды выхода:

| Код | Причина |
|---|---|
| `0` | успех |
| `1` | транспорт: сервер недоступен, таймаут, файл не найден |
| `2` | ошибка сервера: HTTP 400 или `status != "success"` |

Проверка кодов:

```bash
python test_data/test_client.py --file /tmp/bsneg/signal.dat;  echo "код: $?"   # 2
python test_data/test_client.py --url http://127.0.0.1:9999;   echo "код: $?"   # 1
```

> Если нужен GUI вместо PNG: скрипт принудительно использует backend `Agg`
> (без окна). Это сделано специально, чтобы он работал по SSH и в CI.

---

## 10. Шаг 8. Синтетическая ЭКГ

Генератор не требует NumPy и пишет файл в том же формате, что и реальная запись.

```bash
python test_data/synthetic_ecg_generator.py
```

Ожидаемо: файл `test_data/synthetic_signal.txt`, 6 сокращений, ЧСС 72 BPM,
1458 отсчётов, 5.832 с при 250 Гц.

Проверка через сервер:

```bash
python test_data/test_client.py --file test_data/synthetic_signal.txt --no-plots
```

Ожидается 6 событий и `heart_rate_bpm ≈ 72`.

Другие сценарии:

```bash
# 10 сокращений при 90 BPM
python test_data/synthetic_ecg_generator.py --beats 10 --heart-rate 90 \
       --output test_data/synthetic_90bpm.txt

# без шума и дрейфа — «идеальная» ЭКГ для сверки математики
python test_data/synthetic_ecg_generator.py --noise 0 --drift 0 \
       --output test_data/synthetic_clean.txt

# две колонки: время и сигнал (проверка параметра column)
python test_data/synthetic_ecg_generator.py --with-time-column \
       --output /tmp/two_columns.txt
```

Все опции: `--output`, `--beats`, `--fs`, `--amplitude`, `--heart-rate`,
`--noise`, `--drift`, `--seed`, `--with-time-column`.

---

## 11. Шаг 9. Запуск и проверка в Docker

### 11.1 Предварительная проверка

```bash
docker info --format '{{.ServerVersion}} / {{.OperatingSystem}}'
```

Если демон не запущен — `Cannot connect to the Docker daemon`: запустите Docker
Desktop / OrbStack / `sudo systemctl start docker`.

### 11.2 Сборка и запуск

```bash
docker compose up --build -d
```

Первая сборка занимает несколько минут: скачивается `python:3.14-slim`,
ставится `libgomp1` и все пакеты из `requirements.txt`. Повторная сборка
переиспользует слой зависимостей, пока `requirements.txt` не менялся.

### 11.3 Проверка статуса

```bash
docker compose ps
```

Ожидается:

```
NAME                  IMAGE                                              STATUS                    PORTS
biosignal-processor   biosignal-processor-gerasimenko-python-biosignal   Up 16 seconds (healthy)   0.0.0.0:8000->8000/tcp
```

Ключевое — `(healthy)`. `healthcheck` опрашивает `GET /variant` каждые 30 с,
первая проверка — через 10 с после старта (`start-period`). Если статус
`(health: starting)`, подождите 10–40 с и повторите `docker compose ps`.

### 11.4 Те же проверки, что и локально

```bash
curl -s -o /dev/null -w "variant: %{http_code}\n" http://127.0.0.1:8000/variant
curl -F "file=@test_data/raw_signal.txt" "http://127.0.0.1:8000/analyze?fs=250" -o /tmp/analyze_docker.json
python -c "import json;d=json.load(open('/tmp/analyze_docker.json'));print(d['status'], len(d['detected_events']), d['calculated_features']['mean_qrs_width_ms'], d['calculated_features']['max_peak_amplitude'], d['calculated_features']['heart_rate_bpm'])"
```

Ожидается:

```
success 6 88.666667 0.995602 70.754717
```

Клиент против контейнера:

```bash
python test_data/test_client.py --no-plots
```

### 11.5 Логи

```bash
docker compose logs -f            # потоком
docker compose logs --tail=50     # последние 50 строк
```

Ожидаемо — только `INFO`: старт uvicorn, `GET /variant` 200, `POST /analyze` 200,
негативные запросы `400 Bad Request`. Стектрейсов и `ERROR` быть не должно.

### 11.6 Остановка

```bash
docker compose down
```

Удаляются контейнер и сеть; образ остаётся. Полная очистка:

```bash
docker compose down --rmi local
docker builder prune
```

### 11.7 Без compose

```bash
docker build -t biosignal-processor .
docker run --rm -p 8000:8000 biosignal-processor
```

Проверка — те же `curl`-команды. В `docker run` healthcheck тоже работает:

```bash
docker inspect --format '{{.State.Health.Status}}' $(docker ps -q --filter ancestor=biosignal-processor)
```

### 11.8 Что внутри образа и почему

| Решение | Причина |
|---|---|
| `python:3.14-slim`, не `alpine` | для колёс SciPy/NumPy нужен glibc (manylinux), на musl колёс нет |
| `apt-get install libgomp1` | без него SciPy падает: `libgomp.so.1: cannot open shared object file` |
| сначала `COPY requirements.txt`, потом `COPY . .` | правка кода не инвалидирует слой с зависимостями |
| `useradd -m appuser` + `USER appuser` | приложение не работает от root |
| `HEALTHCHECK` через `urllib` | в slim нет `curl`, но есть стандартная библиотека |
| `PYTHONUNBUFFERED=1` | логи видны сразу, а не пачкой после буфера |

---

## 12. Полный чек-лист приёмки

Отмечайте по порядку; каждый пункт — команда и ожидаемый результат.

- [ ] **1. Окружение.** `python -c "import numpy, scipy, fastapi"` → без ошибок, `ok 2.5.4 1.18.1`.
- [ ] **2. Ядро без веба.** `python -c "import signal_processor"` → без ошибок (FastAPI в модуль не импортируется).
- [ ] **3. Сервер поднят.** `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/variant` → `200`.
- [ ] **4. Swagger.** `http://127.0.0.1:8000/docs` открывается, `POST /analyze` виден.
- [ ] **5. OpenAPI.** `curl -s http://127.0.0.1:8000/openapi.json | head -c 200` → JSON со схемами.
- [ ] **6. Основной анализ.** `POST /analyze?fs=250` → 6 событий, границы 108–127 … 1165–1190.
- [ ] **7. Признаки.** `mean_qrs_width_ms ≈ 88.67`, `max_peak_amplitude ≈ 0.9956`, `heart_rate_bpm ≈ 70.75`.
- [ ] **8. Автосверка.** скрипт из §7 → `OK: 6 событий …`.
- [ ] **9. Ошибки.** все шесть сценариев из §8 → HTTP 400 и правильный код.
- [ ] **10. Клиент.** `python test_data/test_client.py` → таблицы, 6 событий, два PNG.
- [ ] **11. Коды клиента.** `.dat` → 2, закрытый порт → 1.
- [ ] **12. Синтетика.** генератор + клиент `--no-plots` → 6 событий, ЧСС ≈ 72.
- [ ] **13. Многоколоночность.** `column=1` на файле с колонкой времени → 4 события, 90 BPM.
- [ ] **14. Docker.** `docker compose up --build -d` → `docker compose ps` показывает `(healthy)`.
- [ ] **15. Docker-анализ.** те же `curl` к контейнеру → те же 6 событий и числа.
- [ ] **16. Логи.** `docker compose logs --tail=50` → без `ERROR` и стектрейсов.
- [ ] **17. Остановка.** `docker compose down` → контейнер и сеть удалены.
- [ ] **18. Git.** `git branch` → только `dev`; `git log --oneline` → ≥3 коммитов; `git status` чистый.

---

## 13. Диагностика проблем

| Симптом | Причина | Решение |
|---|---|---|
| `externally-managed-environment` при `pip install` | PEP 668: ставите в системный Python | создайте и активируйте `venv`, ставьте внутрь него |
| `ModuleNotFoundError: No module named 'fastapi'` | `venv` не активирован | `source venv/bin/activate`, проверьте `which python` |
| `ImportError: libgomp.so.1: cannot open shared object file` | в образе нет OpenMP-рантайма | в `Dockerfile` должен быть `libgomp1`; пересоберите `docker compose build --no-cache` |
| `Address already in use` / порт 8000 занят | другой процесс или старый контейнер | `lsof -nP -iTCP:8000 -sTCP:LISTEN`, `pkill -f "uvicorn app:app"`, `docker compose down` |
| `docker: Cannot connect to the Docker daemon` | демон не запущен | запустите Docker Desktop / OrbStack |
| `docker compose ps` → `(unhealthy)` | приложение не отвечает на `/variant` | `docker compose logs --tail=50`; проверьте, что в контейнере стартовал uvicorn |
| `docker compose ps` → `(health: starting)` дольше минуты | медленный старт/ошибка импорта | `docker compose logs`; проверьте `libgomp1` и `requirements.txt` |
| `curl: (7) Failed to connect` | сервер не запущен или другой порт | поднимите uvicorn, проверьте `--port` и `--url` у клиента |
| `curl: (52) Empty reply` | процесс упал при импорте | смотрите лог uvicorn: обычно несовместимая версия пакета |
| `HTTP 422` на `/analyze` | `fs` не число (`fs=abc`) | FastAPI отклоняет невалидный тип до нашей валидации; передайте число |
| `HTTP 400 INVALID_FILE_FORMAT` | расширение не `.txt`/`.csv` | переименуйте файл, расширение проверяется по имени |
| `HTTP 400 PARSE_ERROR` | в файле текст, `,` как десятичный разделитель, BOM в не-UTF8 | числа через точку, кодировка UTF-8; запятая — только разделитель колонок |
| `HTTP 400 INVALID_COLUMN` | в файле меньше колонок, чем `column` | проверьте `column` (с 0) и разделители |
| `HTTP 400 EMPTY_FILE` | файл пуст или только пробелы | проверьте, что файл реально скачан/скопирован |
| `HTTP 400 SIGNAL_TOO_SHORT` | меньше 10 отсчётов | подайте полноценную запись |
| `heart_rate_bpm: null` | найдено меньше двух QRS | это не ошибка: RR не определён; проверьте `fs` и качество сигнала |
| PNG не создаются | нет прав на `test_data/plots` | `--output-dir /tmp/plots` |
| `test_client.py` печатает «Сервер недоступен» | сервер не поднят или не тот порт | запустите uvicorn, сверьте `--url` |
| Графики «пустые»/нет зон QRS | в ответе нет событий | проверьте `fs`: при неверной частоте детектор не находит QRS |

Быстрый сбор диагностики одной командой:

```bash
python --version; which python; \
curl -s -o /dev/null -w "variant: %{http_code}\n" http://127.0.0.1:8000/variant; \
docker compose ps 2>/dev/null; \
docker compose logs --tail=20 2>/dev/null
```

---

## 14. Что и где менять

Все параметры варианта — в `config.py`, без правки алгоритмов:

| Константа | Значение | Что меняет |
|---|---|---|
| `MOVING_AVERAGE_WINDOW` | 7 | окно сглаживания, отсчётов |
| `HIGHPASS_CUTOFF_HZ` | 0.5 | частота среза ФВЧ, Гц |
| `HIGHPASS_ORDER` | 2 | порядок Баттерворта |
| `QRS_ENERGY_THRESHOLD_RATIO` | 0.10 | порог границ QRS (10 %) |
| `R_PEAK_ENERGY_THRESHOLD_RATIO` | 0.30 | порог детектора R-пиков |
| `R_PEAK_REFRACTORY_MS` | 200 | рефрактерный период, мс |
| `QRS_SEARCH_BEFORE_MS` / `QRS_SEARCH_AFTER_MS` | 120 / 160 | окно поиска границ |
| `MIN_QRS_WIDTH_MS` / `MAX_QRS_WIDTH_MS` | 40 / 200 | физиологичные пределы ширины |
| `DEFAULT_SAMPLING_RATE_HZ` | 250 | `fs` по умолчанию |
| `MIN_SAMPLING_RATE_HZ` / `MAX_SAMPLING_RATE_HZ` | 1 / 10000 | допустимый диапазон `fs` |
| `MIN_SIGNAL_SAMPLES` | 10 | минимальная длина записи |
| `SERVER_HOST` / `SERVER_PORT` | 127.0.0.1 / 8000 | локальный запуск `python app.py` |

Где что лежит:

- **маршруты, валидация, формат ошибок** — `app.py`;
- **фильтрация, детекция, признаки** — `signal_processor.py` (без FastAPI);
- **клиент и графики** — `test_data/test_client.py`;
- **синтетика** — `test_data/synthetic_ecg_generator.py`.

> После изменения констант эталонные числа §7 изменятся — сверяйте с новым
> ожидаемым результатом, а не со старым.

---

## 15. Git-процесс

Работа ведётся только в ветке `dev`; `main`/`master` не создаются.

```bash
git branch                 # * dev
git log --oneline
git status                 # чисто
```

Ожидаемая история:

```
ca175ae build: добавить Dockerfile и docker-compose для запуска сервера
18a2fa6 feat: собрать REST API, документацию и клиент тестирования
c4a4048 feat: реализовать фильтрацию, детекцию QRS и расчёт признаков
11671a3 chore: инициализировать каркас FastAPI-сервера и зависимости
```

Правила:

- сообщения — Conventional Commits (`chore:`, `feat:`, `build:`, `docs:`), без `Co-Authored-By`;
- в репозиторий не попадают `venv/`, `__pycache__/`, `test_data/plots/`, логи;
- перед сдачей: `git status` чистый, ветка одна — `dev`.

---

## 16. Справочник API

### `POST /analyze`

`multipart/form-data`, параметры:

| Имя | Где | Тип | По умолчанию | Ограничения |
|---|---|---|---|---|
| `file` | тело | файл | — | `.txt`, `.csv`; ≥10 отсчётов |
| `fs` | query | float | 250 | 1…10000 |
| `column` | query | int | 0 | ≥0, не больше числа колонок |

Успешный ответ — `200`:

```json
{
  "status": "success",
  "fs": 250.0,
  "variant": "4",
  "signal_length": 1250,
  "raw_signal": ["… 1250 чисел …"],
  "filtered_signal": ["… 1250 чисел …"],
  "detected_events": [
    {"type": "QRS_COMPLEX", "r_peak_index": 116, "onset_index": 108, "offset_index": 127,
     "onset_time_ms": 432.0, "offset_time_ms": 508.0, "width_ms": 76.0}
  ],
  "calculated_features": {
    "mean_qrs_width_ms": 88.666667,
    "max_peak_amplitude": 0.995602,
    "mean_amplitude": 1.7e-05,
    "std_amplitude": 0.172234,
    "heart_rate_bpm": 70.754717,
    "r_peak_count": 6,
    "qrs_count": 6
  }
}
```

Ошибка — `400`:

```json
{"error": "КОД", "errorDetails": {"code": "КОД", "details": "текст"}}
```

| Код | Когда |
|---|---|
| `INVALID_FILE_FORMAT` | расширение не `.txt`/`.csv` |
| `EMPTY_FILE` | файл пуст или только пробелы |
| `INVALID_SAMPLING_RATE` | `fs` вне 1…10000 или не число |
| `INVALID_COLUMN` | колонки с таким индексом нет / отрицательный индекс |
| `SIGNAL_TOO_SHORT` | меньше 10 отсчётов |
| `PARSE_ERROR` | строка не является числом / файл не UTF-8 |

### `GET /variant`

Возвращает `variant`, `title`, `signal_type`, `default_fs`, `filtering`
(`moving_average_window`, `highpass`), `qrs_detection` (пороги и окна) и список
`features`.

### Служебные маршруты

| Маршрут | Назначение |
|---|---|
| `/docs` | Swagger UI |
| `/openapi.json` | OpenAPI-схема (используется healthcheck-ом в Docker) |

---

## 17. Ограничения

- `fs` по умолчанию 250 Гц. Для записи с другой частотой её нужно передать явно,
  иначе временные признаки поедут пропорционально.
- `max_peak_amplitude` — знаковый максимум по отфильтрованному сигналу; для
  инвертированного отведения выброс может оказаться в минимуме.
- Ответ содержит сигналы целиком: на очень длинных записях JSON большой,
  пагинации нет.
- Аутентификации и rate limiting нет — сервер учебный, рассчитан на локальный
  запуск.
- Детектор настроен на типичную ЭКГ (≈30–200 BPM); для фибрилляции, трепетания и
  кардиостимулятора пороги нужно подбирать отдельно.
