from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.logging import configure_logging
from app.routers.acceptance import router as acceptance_router
from app.routers.advanced_schedule import router as advanced_schedule_router
from app.routers.attachments import router as attachments_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.identity import router as identity_router
from app.routers.integrations import router as integrations_router
from app.routers.notifications import router as notifications_router
from app.routers.operations import router as operations_router
from app.routers.people import router as people_router
from app.routers.personalized_plans import router as personalized_plans_router
from app.routers.pilot_issues import router as pilot_issues_router
from app.routers.pilotage import router as pilotage_router
from app.routers.progress import router as progress_router
from app.routers.readiness import router as readiness_router
from app.routers.schedule import router as schedule_router
from app.routers.transmissions import router as transmissions_router
from app.routers.work import router as work_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="Transmissions API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(attachments_router)
app.include_router(acceptance_router)
app.include_router(advanced_schedule_router)
app.include_router(identity_router)
app.include_router(integrations_router)
app.include_router(notifications_router)
app.include_router(operations_router)
app.include_router(people_router)
app.include_router(personalized_plans_router)
app.include_router(pilotage_router)
app.include_router(pilot_issues_router)
app.include_router(readiness_router)
app.include_router(progress_router)
app.include_router(schedule_router)
app.include_router(transmissions_router)
app.include_router(work_router)
