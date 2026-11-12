"""Зависимости FastAPI: готовые экземпляры компонентов.

Компоненты не хранят состояния, поэтому создаются один раз на процесс.
Подмена в тестах — через ``dependency_overrides`` FastAPI.
"""

from __future__ import annotations

from functools import lru_cache

from biosignal.api.response import AnalysisResponseBuilder
from biosignal.io.parser import SignalTextParser
from biosignal.io.validators import AnalysisRequestValidator
from biosignal.processing.pipeline import EcgPipeline


@lru_cache(maxsize=1)
def get_pipeline() -> EcgPipeline:
    """Конвейер обработки сигнала."""
    return EcgPipeline()


@lru_cache(maxsize=1)
def get_parser() -> SignalTextParser:
    """Разборщик файла с отсчётами."""
    return SignalTextParser()


@lru_cache(maxsize=1)
def get_validator() -> AnalysisRequestValidator:
    """Валидатор параметров запроса."""
    return AnalysisRequestValidator()


@lru_cache(maxsize=1)
def get_response_builder() -> AnalysisResponseBuilder:
    """Сборщик успешного ответа."""
    return AnalysisResponseBuilder()
