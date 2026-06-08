from fastapi import APIRouter
from . import keys, users, monitor, providers, knowledge as admin_knowledge

router = APIRouter(prefix="/api/admin", tags=["admin"])
router.include_router(keys.router)
router.include_router(users.router)
router.include_router(monitor.router)
router.include_router(providers.router)
router.include_router(admin_knowledge.router)
