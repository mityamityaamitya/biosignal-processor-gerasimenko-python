"""Ошибки предметной области, не зависящие от HTTP.

Слой ввода-вывода сообщает об ошибке кодом из ``config`` и пояснением; слой API
превращает её в HTTP 400 с единым телом ответа.
"""

from __future__ import annotations


class SignalInputError(ValueError):
    """Некорректные входные данные запроса.

    :param code: машиночитаемый код ошибки (константа ``ERROR_*`` из config);
    :param details: человекочитаемое пояснение для поля ``errorDetails.details``.
    """

    def __init__(self, code: str, details: str) -> None:
        super().__init__(details)
        self.code = code
        self.details = details
