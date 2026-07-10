from fastapi import APIRouter

from app.api.routes import health
from app.domains.accounts.router import router as accounts_router
from app.domains.branches.router import router as branches_router
from app.domains.payments.router import router as payments_router
from app.domains.reservations.router import router as reservations_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(accounts_router, tags=["accounts"])
api_router.include_router(branches_router, tags=["branches"])
api_router.include_router(reservations_router, tags=["reservations"])
api_router.include_router(payments_router, tags=["payments"])
