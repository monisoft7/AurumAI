from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:

    APP_NAME = "AurumAI"

    VERSION = "0.0.1"

    DEBUG = True

    TIMEZONE = "UTC"

    FRED_API_KEY = os.getenv("FRED_API_KEY")

    NEWS_API_KEY = os.getenv("NEWS_API_KEY")


settings = Settings()