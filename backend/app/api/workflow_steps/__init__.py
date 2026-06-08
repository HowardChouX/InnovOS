from fastapi import APIRouter
from .demand_portrait import router as demand_router
from .problem_modeling import router as modeling_router

router = APIRouter(prefix="/api/workflow-steps", tags=["workflow-steps"])
router.include_router(demand_router)
router.include_router(modeling_router)
