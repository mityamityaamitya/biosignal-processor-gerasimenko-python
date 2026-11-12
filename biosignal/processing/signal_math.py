"""Чистые функции над массивами: общая математика для фильтров и детекторов.

Модуль не знает ни про конкретные пороги, ни про HTTP: все параметры приходят
аргументами.
"""

from __future__ import annotations

import numpy as np

MILLISECONDS_PER_SECOND = 1000.0


def samples_from_ms(ms: float, fs: float) -> int:
    """Переводит длительность в миллисекундах в число отсчётов (не меньше 1)."""
    return max(1, int(round(ms * fs / MILLISECONDS_PER_SECOND)))


def odd_window_samples(ms: float, fs: float) -> int:
    """Окно сглаживания в отсчётах: нечётное и не меньше 3.

    Центрированное окно без смещения фазы возможно только при нечётной длине.
    """
    samples = samples_from_ms(ms, fs)
    if samples % 2 == 0:
        samples += 1
    return max(3, samples)


def moving_average(data: np.ndarray, window: int) -> np.ndarray:
    """Центрированное скользящее среднее с усечённым окном на краях.

    ``y[i] = mean(x[max(0, i-half) .. min(n-1, i+half)])``, деление — на
    фактическое число доступных отсчётов. Нулями окно не дополняется: иначе на
    краях появился бы ложный провал к нулю. Чётное окно уменьшается до
    ближайшего нечётного.
    """
    values = np.asarray(data, dtype=float)
    size = values.size
    if size == 0:
        return values.copy()
    if window <= 1 or window > size:
        return values.copy()

    effective = window - 1 if window % 2 == 0 else window
    if effective <= 1:
        return values.copy()

    half = effective // 2
    cumulative = np.concatenate(([0.0], np.cumsum(values)))
    indices = np.arange(size)
    left = np.maximum(0, indices - half)
    right = np.minimum(size - 1, indices + half)
    return (cumulative[right + 1] - cumulative[left]) / (right - left + 1)


def derivative_energy(data: np.ndarray) -> np.ndarray:
    """Энергия центральной производной ``((x[i+1] - x[i-1]) / 2)^2``.

    На краях массива производная нулевая — там нет второго соседа.
    """
    energy = np.zeros_like(data)
    if data.size >= 3:
        derivative = (data[2:] - data[:-2]) / 2.0
        energy[1:-1] = derivative * derivative
    return energy


def sliding_window_max(data: np.ndarray, half: int) -> np.ndarray:
    """Максимум в скользящем окне ``[i-half, i+half]`` (края — nearest)."""
    if half <= 0:
        return data.copy()
    from scipy import ndimage

    return ndimage.maximum_filter1d(data, size=2 * half + 1, mode="nearest")
