"""
Synapse — Main FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(train_router, prefix="/api")
app.include_router(network_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")
app.include_router(replay_router, prefix="/api")
app.include_router(corridor_router, prefix="/api")


@app.get("/health")
def health_check():
    from .dependencies import (
        train_state_engine, network_state_engine,
        station_lookup, train_lookup, route_lookup,
    )
    return {
        "status": "ok",
        "stations_loaded": len(station_lookup),
        "trains_loaded": len(train_lookup),
        "routes_loaded": len(route_lookup),
        "network_sections": network_state_engine.total_sections,
        "active_trains": train_state_engine.active_train_count,
    }
