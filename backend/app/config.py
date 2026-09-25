"""
Synapse Backend — FastAPI Application Configuration

Feature flags and application settings loaded from environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Try .env.example as fallback for development
    _example_path = Path(__file__).parent.parent / ".env.example"
    if _example_path.exists():
        load_dotenv(_example_path)


class Settings:
    """Application settings from environment variables."""

    # Paths
    DATA_RAW_DIR: str = os.getenv("DATA_RAW_DIR", str(Path(__file__).parent.parent.parent / "data" / "raw"))
    DATA_PROCESSED_DIR: str = os.getenv("DATA_PROCESSED_DIR", str(Path(__file__).parent.parent.parent / "data" / "processed"))
    MODELS_DIR: str = os.getenv("MODELS_DIR", str(Path(__file__).parent.parent.parent / "data" / "models"))

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Feature flags — independently switchable
    ENABLE_WHAT_IF: bool = os.getenv("ENABLE_WHAT_IF", "true").lower() == "true"
    ENABLE_PROPAGATION: bool = os.getenv("ENABLE_PROPAGATION", "true").lower() == "true"
    ENABLE_WEATHER: bool = os.getenv("ENABLE_WEATHER", "false").lower() == "true"
    ENABLE_NETWORK_GRAPH: bool = os.getenv("ENABLE_NETWORK_GRAPH", "true").lower() == "true"
    ENABLE_OPERATIONAL_CONFLICTS: bool = os.getenv("ENABLE_OPERATIONAL_CONFLICTS", "true").lower() == "true"

    # Weather API
    WEATHER_API_BASE: str = os.getenv("WEATHER_API_BASE", "https://api.open-meteo.com/v1")

    # Security
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "dev-only-change-in-production")
    CONTROL_ROOM_AUTH_ENABLED: bool = os.getenv("CONTROL_ROOM_AUTH_ENABLED", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Model
    MODEL_VERSION: str = "v1.0.0"

    # Replay
    DEFAULT_REPLAY_TICK_SECONDS: int = 60  # 1 minute per tick in replay

    # Timezone
    TIMEZONE: str = "Asia/Kolkata"

    # Stability thresholds (documented methodology)
    # STABLE: variance of last N predictions < 2 min
    # SETTLING: variance between 2-5 min
    # VOLATILE: variance > 5 min
    STABILITY_STABLE_THRESHOLD: float = 2.0
    STABILITY_VOLATILE_THRESHOLD: float = 5.0
    STABILITY_WINDOW_SIZE: int = 5  # Number of recent predictions to consider

    # Data freshness thresholds (seconds)
    FRESH_THRESHOLD: int = 120      # < 2 min = fresh
    STALE_THRESHOLD: int = 600      # > 10 min = stale
    DEAD_THRESHOLD: int = 1800      # > 30 min = dead/fallback


settings = Settings()
