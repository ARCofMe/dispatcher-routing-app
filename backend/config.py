import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BLUEFOLDER_BASE_URL = os.getenv("BLUEFOLDER_BASE_URL")
    BLUEFOLDER_API_KEY = os.getenv("BLUEFOLDER_API_KEY")
    MAPS_PROVIDER = os.getenv("MAPS_PROVIDER", "google")
    DEBUG = bool(int(os.getenv("DEBUG", "1")))

config = Config()
