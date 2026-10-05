from functools import lru_cache

from app.services.pipeline import HLDService


@lru_cache
def get_service() -> HLDService:
    return HLDService()
