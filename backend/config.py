import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on", "debug", "development")


class Config:
    BLUEFOLDER_BASE_URL = os.getenv("BLUEFOLDER_BASE_URL")
    BLUEFOLDER_API_KEY = os.getenv("BLUEFOLDER_API_KEY")
    MAPS_PROVIDER = os.getenv("MAPS_PROVIDER", "google")
    DEBUG = _env_bool("DEBUG", default=True)

config = Config()
