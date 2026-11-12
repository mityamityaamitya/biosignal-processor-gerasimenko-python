"""Пакет обработки биосигналов (вариант 4, ЭКГ).

Слои пакета не зависят от веб-фреймворка:

- ``biosignal.processing`` — математика: фильтры, детекторы, признаки, конвейер;
- ``biosignal.io`` — разбор входного файла и валидация запроса;
- ``biosignal.api`` — FastAPI: маршруты, схемы, обработка ошибок.

Корневые ``app.py`` и ``signal_processor.py`` — тонкие фасады для запуска и для
совместимости с шаблоном задания.
"""

from biosignal.processing import (
    ButterworthHighPassFilter,
    EcgPipeline,
    FeatureExtractor,
    MovingAverageFilter,
    ProcessingResult,
    QrsBoundaryDetector,
    QrsComplex,
    RPeakDetector,
    SignalFeatures,
)

__all__ = [
    "ButterworthHighPassFilter",
    "EcgPipeline",
    "FeatureExtractor",
    "MovingAverageFilter",
    "ProcessingResult",
    "QrsBoundaryDetector",
    "QrsComplex",
    "RPeakDetector",
    "SignalFeatures",
]
