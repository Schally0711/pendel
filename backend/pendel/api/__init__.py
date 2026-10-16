from fastapi import APIRouter

from . import absences, account, admin, clock, records, reports, settings

router = APIRouter(prefix="/api")
for module in (account, admin, settings, records, clock, reports, absences):
    router.include_router(module.router)
