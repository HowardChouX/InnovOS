from fastapi import APIRouter

from . import (
    failover,
    knowledge as admin_knowledge,
    monitor,
    patent_db,
    providers,
    settings,
    usage,
    user_model_services,
    users,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
router.include_router(users.router)
router.include_router(monitor.router)
router.include_router(providers.router)
router.include_router(admin_knowledge.router)
router.include_router(settings.router)
router.include_router(patent_db.router)
# New in 2026-07 model-service refactor:
router.include_router(user_model_services.router)
router.include_router(usage.router)
router.include_router(failover.router)
