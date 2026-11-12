"""Разбор входного файла с отсчётами сигнала."""

from __future__ import annotations

import re

import config
from biosignal.errors import SignalInputError


class SignalTextParser:
    """Разбирает текст в строки чисел и выбирает колонку сигнала.

    Поддерживаются файлы ``.txt`` и ``.csv`` с одним числом в строке или
    несколькими колонками; разделители — пробел, таб, запятая, точка с запятой.
    """

    def __init__(self, separators: tuple[str, ...] = config.COLUMN_SEPARATORS) -> None:
        pattern = "[" + re.escape("".join(separators)) + "]+"
        self._split = re.compile(pattern)

    def parse(self, contents: bytes) -> list[list[float]]:
        """Возвращает список строк чисел.

        :raises SignalInputError: файл пуст, не является UTF-8-текстом или
            содержит нечисловые значения.
        """
        if not contents.strip():
            raise SignalInputError(config.ERROR_EMPTY_FILE, "Файл пуст или не содержит данных")

        rows: list[list[float]] = []
        for line_number, line in enumerate(self._decode(contents).splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            tokens = [token for token in self._split.split(stripped) if token]
            if not tokens:
                continue
            try:
                rows.append([float(token) for token in tokens])
            except ValueError as error:
                raise SignalInputError(
                    config.ERROR_PARSE_ERROR,
                    f"Строка {line_number} не является числом: {stripped[:80]!r} ({error})",
                ) from error

        if not rows:
            raise SignalInputError(config.ERROR_EMPTY_FILE, "Файл не содержит ни одной строки с данными")
        return rows

    def extract_column(self, rows: list[list[float]], column: int) -> list[float]:
        """Выбирает колонку сигнала из разобранных строк.

        :raises SignalInputError: колонки с таким индексом нет.
        """
        for line_number, row in enumerate(rows, start=1):
            if column >= len(row):
                raise SignalInputError(
                    config.ERROR_INVALID_COLUMN,
                    f"Колонка {column} отсутствует: в строке {line_number} "
                    f"только {len(row)} колонок(и)",
                )
        return [row[column] for row in rows]

    @staticmethod
    def _decode(contents: bytes) -> str:
        try:
            return contents.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise SignalInputError(
                config.ERROR_PARSE_ERROR,
                f"Файл не является текстом в кодировке UTF-8: {error}",
            ) from error
