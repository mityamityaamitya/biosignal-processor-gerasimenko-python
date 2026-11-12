"""Валидация параметров запроса на анализ."""

from __future__ import annotations

import math

import config
from biosignal.errors import SignalInputError


class AnalysisRequestValidator:
    """Проверяет расширение файла, частоту дискретизации, колонку и длину сигнала."""

    def validate_filename(self, filename: str | None) -> None:
        """Разрешены только расширения из :data:`config.ALLOWED_FILE_EXTENSIONS`."""
        name = (filename or "").lower()
        if not name.endswith(config.ALLOWED_FILE_EXTENSIONS):
            raise SignalInputError(
                config.ERROR_INVALID_FILE_FORMAT,
                "Неверный формат файла: разрешены только "
                + " и ".join(config.ALLOWED_FILE_EXTENSIONS),
            )

    def validate_sampling_rate(self, fs: float) -> None:
        """Частота дискретизации должна лежать в допустимом диапазоне."""
        if not math.isfinite(fs) or not (
            config.MIN_SAMPLING_RATE_HZ <= fs <= config.MAX_SAMPLING_RATE_HZ
        ):
            raise SignalInputError(
                config.ERROR_INVALID_SAMPLING_RATE,
                f"Частота дискретизации должна лежать в диапазоне "
                f"{config.MIN_SAMPLING_RATE_HZ:g}…{config.MAX_SAMPLING_RATE_HZ:g} Гц, "
                f"получено {fs}",
            )

    def validate_column(self, column: int) -> None:
        """Индекс колонки не может быть отрицательным."""
        if column < 0:
            raise SignalInputError(
                config.ERROR_INVALID_COLUMN,
                f"Индекс колонки не может быть отрицательным: {column}",
            )

    def validate_signal_length(self, length: int) -> None:
        """Сигнал должен содержать не меньше :data:`config.MIN_SIGNAL_SAMPLES` отсчётов."""
        if length < config.MIN_SIGNAL_SAMPLES:
            raise SignalInputError(
                config.ERROR_SIGNAL_TOO_SHORT,
                f"Сигнал слишком короткий: {length} отсчётов, "
                f"нужно не меньше {config.MIN_SIGNAL_SAMPLES}",
            )
