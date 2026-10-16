from fastapi import APIRouter

from . import account, admin, clock, records, reports, settings

router = APIRouter(prefix="/api")
for module in (account, admin, settings, records, clock, reports):
    router.include_router(module.router)
