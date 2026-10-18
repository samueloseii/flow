from fastapi import APIRouter

from app.api.endpoints import (
    analytics,
    auth,
    billing,
    communities,
    dashboard,
    expenses,
    households,
    maintenance,
    meters,
    partners,
    readings,
    sync,
    tariffs,
    water_committees,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(partners.router)
api_router.include_router(communities.router)
api_router.include_router(households.router)
api_router.include_router(meters.router)
api_router.include_router(billing.router)
api_router.include_router(maintenance.router)
api_router.include_router(expenses.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(sync.router)
api_router.include_router(water_committees.router)
api_router.include_router(tariffs.router)
api_router.include_router(readings.router)
