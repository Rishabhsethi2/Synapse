"""
Synapse — Main FastAPI Application
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .api.routes_train import router as train_router
from .api.routes_network import router as network_router
from .api.routes_intelligence import router as intelligence_router
from .api.routes_replay import router as replay_router
from .corridor.routes import router as corridor_router
from .dependencies import startup_load_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data and initialize engines at startup."""
    logger.info("Synapse starting up...")
    try:
        startup_load_data()
    except Exception as e:
        logger.error("Startup data loading failed: %s", e, exc_info=True)
        logger.warning("Synapse will start with empty data. Use /api/replay endpoints.")
    yield
    logger.info("Synapse shutting down.")


app = FastAPI(
    title="Synapse API",
    description="Dynamic railway ETA intelligence system for Indian Railways — SIH26028",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    # Credentialed requests cannot use a wildcard origin in browsers.
    allow_credentials=allowed_origin != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(train_router, prefix="/api")
app.include_router(network_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")
app.include_router(replay_router, prefix="/api")
app.include_router(corridor_router, prefix="/api")


@app.get("/health", response_class=PlainTextResponse, include_in_schema=False)
def health_check():
    """Lightweight liveness probe for hosting platforms."""
    return "OK"
