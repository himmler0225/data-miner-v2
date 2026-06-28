from fastapi import APIRouter

from .system import router as system_router

router = APIRouter(prefix="/admin")
router.include_router(system_router, tags=["Admin"])

__all__ = ["router"]
