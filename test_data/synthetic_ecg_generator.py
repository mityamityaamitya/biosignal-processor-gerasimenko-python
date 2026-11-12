#!/usr/bin/env python3
"""Генератор синтетической ЭКГ для проверки сервера без реальной записи.

Скрипт собирает сигнал из набора гауссовых «волн» (P, Q, R, S, T), добавляет
медленный дрейф изолинии и шум, после чего сохраняет результат в текстовый файл
в том же формате, что и ``test_data/raw_signal.txt``: одно число на строку.

Зависимости: только стандартная библиотека Python 3.14 (numpy не нужен).

Примеры::

    # 6 сокращений, fs = 250 Гц, амплитуда R = 1.0
    ./venv/bin/python test_data/synthetic_ecg_generator.py

    # 10 сокращений при 90 BPM, две колонки (время и сигнал) для проверки column
    ./venv/bin/python test_data/synthetic_ecg_generator.py --beats 10 --heart-rate 90 --with-time-column

    # сигнал без шума и дрейфа, чтобы сверить математику с эталоном
    ./venv/bin/python test_data/synthetic_ecg_generator.py --noise 0 --drift 0

Полученный файл отправляется на сервер клиентом ``test_data/test_client.py``.
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "test_data" / "synthetic_signal.txt"

DEFAULT_BEATS = 6
DEFAULT_FS = 250.0
DEFAULT_AMPLITUDE = 1.0
DEFAULT_HEART_RATE_BPM = 72.0
DEFAULT_NOISE = 0.01
DEFAULT_DRIFT = 0.15
DEFAULT_SEED = 42
DECIMAL_PLACES = 3

#: Сколько знаков после запятой писать в колонке времени (на один больше сигнала).
TIME_DECIMAL_PLACES = DECIMAL_PLACES + 1

# Модель одного сокращения: (смещение от R, мс; амплитуда в долях R; СКО, мс).
# Смещения и ширины взяты из типичной морфологии ЭКГ взрослого человека.
ECG_WAVES = (
    ("P", -200.0, 0.12, 25.0),
    ("Q", -25.0, -0.12, 8.0),
    ("R", 0.0, 1.00, 10.0),
    ("S", 28.0, -0.25, 10.0),
    ("T", 280.0, 0.30, 45.0),
)

# Частоты медленного дрейфа изолинии (дыхание и движение электрода), Гц.
DRIFT_COMPONENTS_HZ = (0.15, 0.30)
MILLISECONDS_PER_SECOND = 1000.0
SECONDS_PER_MINUTE = 60.0

# Границы валидации аргументов командной строки.
MIN_BEATS = 1


def gaussian(x_ms: float, center_ms: float, amplitude: float, sigma_ms: float) -> float:
    """Одногорбая волна: ``A · exp(−(x − c)² / (2σ²))``."""
    delta = x_ms - center_ms
    return amplitude * math.exp(-(delta * delta) / (2.0 * sigma_ms * sigma_ms))


def beat_value(time_ms: float, amplitude: float) -> float:
    """Значение одного сердечного сокращения в момент ``time_ms`` от его R-пика."""
    return sum(
        gaussian(time_ms, offset_ms, amplitude * wave_amplitude, sigma_ms)
        for _, offset_ms, wave_amplitude, sigma_ms in ECG_WAVES
    )


def baseline_drift(time_s: float, drift_amplitude: float) -> float:
    """Медленный дрейф изолинии — сумма двух низкочастотных синусоид."""
    return sum(
        drift_amplitude * math.sin(2.0 * math.pi * frequency_hz * time_s) / len(DRIFT_COMPONENTS_HZ)
        for frequency_hz in DRIFT_COMPONENTS_HZ
    )


def build_signal(
    beats: int,
    fs: float,
    amplitude: float,
    heart_rate_bpm: float,
    noise: float,
    drift: float,
    seed: int,
) -> list[float]:
    """Возвращает список отсчётов синтетической ЭКГ.

    Первый R-пик ставится через один интервал RR от начала записи, последний —
    за один интервал RR до конца: так начало и конец сигнала не обрезают
    комплексы, и детектор не теряет краевые R-пики.
    """
    rr_ms = SECONDS_PER_MINUTE * MILLISECONDS_PER_SECOND / heart_rate_bpm
    first_r_ms = rr_ms
    duration_ms = first_r_ms + (beats - 1) * rr_ms + rr_ms
    sample_count = int(round(duration_ms / MILLISECONDS_PER_SECOND * fs))

    rng = random.Random(seed)
    signal: list[float] = []

    for index in range(sample_count):
        time_ms = index * MILLISECONDS_PER_SECOND / fs
        time_s = time_ms / MILLISECONDS_PER_SECOND

        value = baseline_drift(time_s, drift)
        for beat in range(beats):
            r_peak_ms = first_r_ms + beat * rr_ms
            value += beat_value(time_ms - r_peak_ms, amplitude)

        if noise > 0.0:
            value += rng.gauss(0.0, noise)

        signal.append(value)

    return signal


def format_line(index: int, value: float, fs: float, with_time_column: bool) -> str:
    """Строка файла: только сигнал или время и сигнал через пробел."""
    if with_time_column:
        time_s = index / fs
        return f"{time_s:.{TIME_DECIMAL_PLACES}f} {value:.{DECIMAL_PLACES}f}"
    return f"{value:.{DECIMAL_PLACES}f}"


def write_signal(
    signal: list[float],
    output_path: Path,
    fs: float,
    with_time_column: bool,
) -> None:
    """Записывает отсчёты в текстовый файл (одно число или две колонки на строку)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [format_line(index, value, fs, with_time_column) for index, value in enumerate(signal)]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    """Собирает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Генерирует синтетическую ЭКГ в формате, который понимает POST /analyze.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Куда сохранить файл")
    parser.add_argument("--beats", type=int, default=DEFAULT_BEATS, help="Число сокращений (R-пиков)")
    parser.add_argument("--fs", type=float, default=DEFAULT_FS, help="Частота дискретизации, Гц")
    parser.add_argument("--amplitude", type=float, default=DEFAULT_AMPLITUDE, help="Амплитуда R-зубца")
    parser.add_argument(
        "--heart-rate",
        type=float,
        default=DEFAULT_HEART_RATE_BPM,
        help="Целевая ЧСС, BPM (задаёт расстояние между R-пиками)",
    )
    parser.add_argument("--noise", type=float, default=DEFAULT_NOISE, help="СКО гауссова шума")
    parser.add_argument("--drift", type=float, default=DEFAULT_DRIFT, help="Амплитуда дрейфа изолинии")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Зерно генератора шума")
    parser.add_argument(
        "--with-time-column",
        action="store_true",
        help="Писать две колонки: время в секундах и значение (проверка параметра column)",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Проверяет физический смысл аргументов; при ошибке завершает работу."""
    if args.beats < MIN_BEATS:
        raise SystemExit(f"--beats должно быть не меньше {MIN_BEATS}")
    if args.fs <= 0:
        raise SystemExit("--fs должно быть положительным")
    if args.heart_rate <= 0:
        raise SystemExit("--heart-rate должно быть положительным")


def main() -> int:
    """Генерирует сигнал, сохраняет файл и печатает сводку."""
    args = build_arg_parser().parse_args()
    validate_args(args)

    signal = build_signal(
        beats=args.beats,
        fs=args.fs,
        amplitude=args.amplitude,
        heart_rate_bpm=args.heart_rate,
        noise=args.noise,
        drift=args.drift,
        seed=args.seed,
    )

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    write_signal(signal, output_path, args.fs, args.with_time_column)

    duration_s = len(signal) / args.fs
    columns = "2 (время, сигнал)" if args.with_time_column else "1 (сигнал)"
    print("Синтетическая ЭКГ сохранена")
    print(f"  файл:         {output_path}")
    print(f"  сокращений:   {args.beats} (ЧСС {args.heart_rate:g} BPM)")
    print(f"  отсчётов:     {len(signal)}")
    print(f"  длительность: {duration_s:.{DECIMAL_PLACES}f} с при fs = {args.fs:g} Гц")
    print(f"  колонок:      {columns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
