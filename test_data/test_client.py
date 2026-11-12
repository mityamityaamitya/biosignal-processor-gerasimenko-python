#!/usr/bin/env python3
"""Клиент для проверки REST API сервера обработки биосигналов (вариант 4, ЭКГ).

Скрипт отправляет файл с отсчётами на ``POST /analyze``, печатает рассчитанные
признаки и найденные QRS-комплексы, а затем строит два графика: исходный сигнал
и отфильтрованный с отмеченными границами комплексов и R-пиками.

Зависимости (проверено на версиях из requirements.txt, других не требуется):

    Python      3.14
    requests    2.32.5
    matplotlib  3.10.8

Запуск из корня проекта::

    ./venv/bin/python test_data/test_client.py

Запуск из каталога ``test_data`` (пути вычисляются относительно файла скрипта)::

    cd test_data && ../venv/bin/python test_client.py

Перед запуском сервер должен быть поднят из корня проекта::

    ./venv/bin/python -m uvicorn app:app --port 8000

Коды выхода: 0 — успех, 1 — транспортная ошибка (сервер недоступен, таймаут,
файл не найден), 2 — ошибка обработки на сервере (HTTP 400 или status != success).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

# Без GUI: скрипт должен работать и на машине без графической сессии (CI, ssh).
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (импорт после выбора backend)
import requests  # noqa: E402

# --- Пути и значения по умолчанию -------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
DEFAULT_SIGNAL_FILE = TEST_DATA_DIR / "raw_signal.txt"
DEFAULT_OUTPUT_DIR = TEST_DATA_DIR / "plots"

DEFAULT_URL = "http://127.0.0.1:8000"
ANALYZE_PATH = "/analyze"
DEFAULT_FS = 250.0
DEFAULT_COLUMN = 0

# --- Параметры HTTP и отрисовки ---------------------------------------------

REQUEST_TIMEOUT_SECONDS = 120
MAX_EVENTS_IN_TABLE = 10
FIGURE_SIZE_INCHES = (12.0, 4.5)
FIGURE_DPI = 150
RAW_PLOT_FILENAME = "raw_signal.png"
FILTERED_PLOT_FILENAME = "filtered_signal.png"

# --- Оформление графиков -----------------------------------------------------

RAW_COLOR = "#1f77b4"
FILTERED_COLOR = "#2ca02c"
QRS_SPAN_COLOR = "#ff7f0e"
R_PEAK_COLOR = "#d62728"
QRS_SPAN_ALPHA = 0.25
R_PEAK_MARKER_SIZE = 40
GRID_ALPHA = 0.3

# --- Форматирование чисел ----------------------------------------------------

MILLISECONDS_PER_SECOND = 1000.0
DURATION_DECIMAL_PLACES = 3
EVENT_DECIMAL_PLACES = 1

# --- Коды выхода -------------------------------------------------------------

EXIT_OK = 0
EXIT_TRANSPORT_ERROR = 1
EXIT_BAD_RESPONSE = 2


class ClientError(RuntimeError):
    """Ошибка обмена с сервером, которую нужно показать человеку без трейсбека."""


class TransportError(ClientError):
    """Сервер недоступен или не ответил вовремя (проблема сети, а не данных)."""


# --- Разбор аргументов -------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    """Собирает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Отправляет файл сигнала на POST /analyze и строит графики.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Базовый адрес сервера",
    )
    parser.add_argument(
        "--file",
        default=str(DEFAULT_SIGNAL_FILE),
        help="Файл .txt/.csv с отсчётами сигнала",
    )
    parser.add_argument(
        "--fs",
        type=float,
        default=DEFAULT_FS,
        help="Частота дискретизации сигнала, Гц",
    )
    parser.add_argument(
        "--column",
        type=int,
        default=DEFAULT_COLUMN,
        help="Индекс колонки с сигналом в многоколоночном файле (с 0)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Не строить графики, только напечатать признаки",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Каталог для PNG-файлов с графиками",
    )
    return parser


def resolve_input_path(raw_path: str) -> Path:
    """Находит файл сигнала: сначала относительно текущего каталога, затем проекта."""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path

    from_cwd = Path.cwd() / path
    if from_cwd.exists():
        return from_cwd

    return PROJECT_ROOT / path


def resolve_output_dir(raw_path: str) -> Path:
    """Находит каталог для графиков относительно корня проекта, если путь не абсолютный."""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


# --- HTTP --------------------------------------------------------------------


def call_analyze(url: str, signal_file: Path, fs: float, column: int) -> dict[str, Any]:
    """Отправляет файл на ``POST /analyze`` и возвращает разобранный JSON-ответ."""
    endpoint = url.rstrip("/") + ANALYZE_PATH
    try:
        with signal_file.open("rb") as handle:
            response = requests.post(
                endpoint,
                files={"file": (signal_file.name, handle, "text/plain")},
                params={"fs": fs, "column": column},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
    except requests.ConnectionError as error:
        raise TransportError(
            f"Сервер недоступен по адресу {endpoint}.\n"
            "Проверьте, что uvicorn app:app запущен на порту 8000 "
            "(./venv/bin/python -m uvicorn app:app --port 8000) "
            "и порт не занят другим процессом.\n"
            f"Детали: {error}"
        ) from error
    except requests.Timeout as error:
        raise TransportError(
            f"Сервер не ответил за {REQUEST_TIMEOUT_SECONDS} с ({endpoint}). "
            "Возможно, файл слишком большой для текущих лимитов."
        ) from error

    if response.status_code != requests.codes.ok:
        raise ClientError(format_error_response(response))

    try:
        payload = response.json()
    except ValueError as error:
        raise ClientError(f"Сервер вернул не JSON: {response.text[:500]}") from error

    if payload.get("status") != "success":
        raise ClientError(f"Ответ без статуса success: {json.dumps(payload, ensure_ascii=False)[:500]}")

    return payload


def format_error_response(response: requests.Response) -> str:
    """Печатает тело ошибки в платформенном формате ``error`` / ``errorDetails``."""
    try:
        body = json.dumps(response.json(), ensure_ascii=False, indent=2)
    except ValueError:
        body = response.text.strip() or "<пустое тело>"

    return (
        f"Сервер ответил HTTP {response.status_code} ({response.reason}).\n"
        f"Тело ответа:\n{body}"
    )


# --- Печать результатов ------------------------------------------------------


def format_optional(value: Any, suffix: str = "") -> str:
    """Форматирует значение признака; ``None`` означает «не определено»."""
    if value is None:
        return "не определено (< 2 R-пиков)"
    return f"{value}{suffix}"


def print_table(title: str, rows: list[tuple[str, str]], padding: int) -> None:
    """Печатает выровненную таблицу «подпись — значение»."""
    width = max(len(label) for label, _ in rows)
    print(f"\n{title}")
    print("-" * (width + padding))
    for label, value in rows:
        print(f"{label:<{width}}  {value}")


def print_summary(payload: dict[str, Any], signal_file: Path, url: str, column: int) -> None:
    """Печатает параметры обработки: файл, сервер, вариант, fs, длительность."""
    fs = float(payload["fs"])
    signal_length = int(payload["signal_length"])
    duration_s = signal_length / fs if fs else 0.0

    rows = [
        ("Файл", str(signal_file)),
        ("Сервер", url.rstrip("/")),
        ("Вариант", str(payload.get("variant", "—"))),
        ("Частота дискретизации", f"{fs:g} Гц"),
        ("Колонка", str(column)),
        ("Отсчётов", str(signal_length)),
        ("Длительность записи", f"{duration_s:.{DURATION_DECIMAL_PLACES}f} с"),
        ("Событий (QRS)", str(len(payload.get("detected_events", [])))),
    ]
    print_table("Параметры обработки", rows, padding=42)


def print_features(features: dict[str, Any]) -> None:
    """Печатает все признаки варианта 4."""
    rows = [
        ("mean_qrs_width_ms", format_optional(features.get("mean_qrs_width_ms"), " мс")),
        ("max_peak_amplitude", format_optional(features.get("max_peak_amplitude"))),
        ("mean_amplitude", format_optional(features.get("mean_amplitude"))),
        ("std_amplitude", format_optional(features.get("std_amplitude"))),
        ("heart_rate_bpm", format_optional(features.get("heart_rate_bpm"), " BPM")),
        ("r_peak_count", format_optional(features.get("r_peak_count"))),
        ("qrs_count", format_optional(features.get("qrs_count"))),
    ]
    print_table("Рассчитанные признаки", rows, padding=24)


def print_events(events: list[dict[str, Any]]) -> None:
    """Печатает первые события и общее число найденных комплексов."""
    total = len(events)
    print(f"\nОбнаруженные события (всего {total})")
    if total == 0:
        print("QRS-комплексы не найдены.")
        return

    header = (
        f"{'#':>3}  {'R-пик':>7}  {'onset':>7}  {'offset':>7}  "
        f"{'onset, мс':>10}  {'offset, мс':>11}  {'ширина, мс':>11}"
    )
    print(header)
    print("-" * len(header))
    for number, event in enumerate(events[:MAX_EVENTS_IN_TABLE], start=1):
        print(
            f"{number:>3}  {event['r_peak_index']:>7}  {event['onset_index']:>7}  "
            f"{event['offset_index']:>7}  {event['onset_time_ms']:>10.{EVENT_DECIMAL_PLACES}f}  "
            f"{event['offset_time_ms']:>11.{EVENT_DECIMAL_PLACES}f}  "
            f"{event['width_ms']:>11.{EVENT_DECIMAL_PLACES}f}"
        )

    hidden = total - MAX_EVENTS_IN_TABLE
    if hidden > 0:
        print(f"... ещё {hidden} (показаны первые {MAX_EVENTS_IN_TABLE})")


# --- Графики -----------------------------------------------------------------


def time_axis(signal_length: int, fs: float) -> list[float]:
    """Ось времени в секундах: ``i / fs``."""
    return [index / fs for index in range(signal_length)]


def style_axes(axes: Any, title: str, ylabel: str) -> None:
    """Единое оформление осей: подписи по-русски, сетка, без пустых полей."""
    axes.set_title(title)
    axes.set_xlabel("Время, с")
    axes.set_ylabel(ylabel)
    axes.grid(True, alpha=GRID_ALPHA)
    axes.margins(x=0.01)


def plot_raw_signal(payload: dict[str, Any], output_path: Path) -> Path:
    """Строит график исходного сигнала и сохраняет его в PNG."""
    fs = float(payload["fs"])
    raw_signal = [float(value) for value in payload["raw_signal"]]
    times = time_axis(len(raw_signal), fs)

    figure, axes = plt.subplots(figsize=FIGURE_SIZE_INCHES, dpi=FIGURE_DPI)
    axes.plot(times, raw_signal, color=RAW_COLOR, linewidth=1.0)
    style_axes(axes, "Исходный сигнал ЭКГ", "Амплитуда")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


def plot_filtered_signal(payload: dict[str, Any], output_path: Path) -> Path:
    """Строит отфильтрованный сигнал с границами QRS и R-пиками."""
    fs = float(payload["fs"])
    filtered_signal = [float(value) for value in payload["filtered_signal"]]
    times = time_axis(len(filtered_signal), fs)
    events = payload.get("detected_events", [])

    figure, axes = plt.subplots(figsize=FIGURE_SIZE_INCHES, dpi=FIGURE_DPI)
    axes.plot(times, filtered_signal, color=FILTERED_COLOR, linewidth=1.0, label="Отфильтрованный сигнал")

    # Зоны QRS: onset_time_ms/offset_time_ms приходят в миллисекундах.
    qrs_label_used = False
    for event in events:
        onset_s = float(event["onset_time_ms"]) / MILLISECONDS_PER_SECOND
        offset_s = float(event["offset_time_ms"]) / MILLISECONDS_PER_SECOND
        axes.axvspan(
            onset_s,
            offset_s,
            color=QRS_SPAN_COLOR,
            alpha=QRS_SPAN_ALPHA,
            label=None if qrs_label_used else "Границы QRS (onset–offset)",
        )
        qrs_label_used = True

    # R-пики — точки на отфильтрованном сигнале по индексу отсчёта.
    r_peak_times = []
    r_peak_values = []
    for event in events:
        index = int(event["r_peak_index"])
        if 0 <= index < len(filtered_signal):
            r_peak_times.append(times[index])
            r_peak_values.append(filtered_signal[index])

    if r_peak_times:
        axes.scatter(
            r_peak_times,
            r_peak_values,
            s=R_PEAK_MARKER_SIZE,
            color=R_PEAK_COLOR,
            zorder=3,
            label="R-пики",
        )

    style_axes(axes, "Отфильтрованный сигнал с границами QRS-комплексов", "Амплитуда")
    axes.legend(loc="upper right", fontsize="small")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


def save_plots(payload: dict[str, Any], output_dir: Path) -> list[Path]:
    """Строит оба графика в ``output_dir`` и возвращает пути к файлам."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        plot_raw_signal(payload, output_dir / RAW_PLOT_FILENAME),
        plot_filtered_signal(payload, output_dir / FILTERED_PLOT_FILENAME),
    ]


# --- Точка входа -------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Запускает клиент; возвращает код выхода процесса."""
    args = build_arg_parser().parse_args(argv)

    signal_file = resolve_input_path(args.file)
    if not signal_file.is_file():
        print(f"Файл не найден: {signal_file}", file=sys.stderr)
        return EXIT_TRANSPORT_ERROR

    try:
        payload = call_analyze(args.url, signal_file, args.fs, args.column)
    except TransportError as error:
        print(f"\nОшибка: {error}", file=sys.stderr)
        return EXIT_TRANSPORT_ERROR
    except ClientError as error:
        print(f"\nОшибка: {error}", file=sys.stderr)
        return EXIT_BAD_RESPONSE

    print_summary(payload, signal_file, args.url, args.column)
    print_features(payload.get("calculated_features", {}))
    print_events(payload.get("detected_events", []))

    if args.no_plots:
        print("\nГрафики не строились (--no-plots).")
        return EXIT_OK

    output_dir = resolve_output_dir(args.output_dir)
    saved = save_plots(payload, output_dir)
    print("\nГрафики сохранены:")
    for path in saved:
        print(f"  {path}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
