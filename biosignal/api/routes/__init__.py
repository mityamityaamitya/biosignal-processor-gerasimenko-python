"""HTTP-маршруты сервера."""

from biosignal.api.routes.analyze import router as analyze_router
from biosignal.api.routes.variant import router as variant_router

__all__ = ["analyze_router", "variant_router"]
