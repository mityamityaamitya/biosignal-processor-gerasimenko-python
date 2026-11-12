"""Математическое ядро: фильтры, детекторы, признаки и конвейер.

Пакет не импортирует FastAPI/Flask/uvicorn и тестируется отдельно от сети.
"""

from biosignal.processing.detectors import QrsBoundaryDetector, RPeakDetector
from biosignal.processing.features import FeatureExtractor
from biosignal.processing.filters import ButterworthHighPassFilter, MovingAverageFilter
from biosignal.processing.models import ProcessingResult, QrsComplex, SignalFeatures
from biosignal.processing.pipeline import EcgPipeline

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
