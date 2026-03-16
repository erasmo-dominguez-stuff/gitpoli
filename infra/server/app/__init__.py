"""Policy evaluation server — thin bridge between HTTP clients and OPA.

On startup the SQLite audit database is initialised (tables created if absent).
All business logic lives in the routers; this file only wires everything together.
"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .audit import init_db
from .routers import audit_api, evaluate, health, webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Initialise resources on startup and release them on shutdown."""
    init_db()
    yield
    # Nothing to tear down currently; extend here if connection pools are added.


app = FastAPI(title="gitpoli Policy Server", version="1.0.0", lifespan=_lifespan)

app.include_router(health.router)
app.include_router(evaluate.router)
app.include_router(webhook.router)
app.include_router(audit_api.router)
