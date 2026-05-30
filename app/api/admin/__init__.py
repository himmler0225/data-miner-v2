from fastapi import APIRouter
from .system import router as system_router
from .youtube import router as youtube_router

router = APIRouter(prefix="/admin")
router.include_router(system_router, tags=["Admin"])
router.include_router(youtube_router, prefix="/youtube", tags=["Admin - YouTube"])

__all__ = ["router"]
