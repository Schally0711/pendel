from fastapi import APIRouter

from . import absences, account, admin, clock, integrations, records, reports, settings, stats

router = APIRouter(prefix="/api")
for module in (account, admin, settings, records, clock, reports, absences, integrations, stats):
    router.include_router(module.router)
