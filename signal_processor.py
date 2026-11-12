"""Каркас ядра обработки биосигналов (вариант 4, ЭКГ).

Модуль остаётся «чистым»: только NumPy/SciPy/stdlib, без импортов FastAPI/Flask.
Реализация фильтрации, детекции QRS и расчёта признаков — следующий этап.
"""

from __future__ import annotations

import numpy as np

import config


def filter_signal(raw_data: np.ndarray, fs: float, **kwargs) -> np.ndarray:
    """ЗАДАНИЕ: фильтрация сигнала (MA(7) + ФВЧ Баттерворта 0.5 Гц)."""
    raise NotImplementedError


def detect_events(filtered_data: np.ndarray, fs: float, **kwargs) -> list[int]:
    """ЗАДАНИЕ: локализация событий (R-пики и границы QRS-комплексов)."""
    raise NotImplementedError


def extract_features(filtered_data: np.ndarray, event_indices: list[int], fs: float) -> dict:
    """ЗАДАНИЕ: расчёт признаков варианта 4."""
    raise NotImplementedError


def process_biosignal(raw_signal_list: list[float], fs: float = config.DEFAULT_SAMPLING_RATE_HZ) -> dict:
    """Центральная функция управления конвейером обработки."""
    raise NotImplementedError
