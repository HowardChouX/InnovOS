from fastapi import APIRouter

from . import knowledge as admin_knowledge
from . import monitor, patent_db, providers, settings, users

router = APIRouter(prefix="/api/admin", tags=["admin"])
router.include_router(users.router)
router.include_router(monitor.router)
router.include_router(providers.router)
router.include_router(admin_knowledge.router)
router.include_router(settings.router)
router.include_router(patent_db.router)
