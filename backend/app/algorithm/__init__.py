from .ai_client import ai_available
from .zr_ipm import ZRIPMEngine

_engine: ZRIPMEngine | None = None


def get_engine() -> ZRIPMEngine:
    global _engine
    if _engine is None:
        _engine = ZRIPMEngine()
    return _engine
