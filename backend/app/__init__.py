"""
Early bootstrap: load .env and configure logging before any app module evaluates.

Python loads __init__.py when the `app` package is first imported. Putting
load_dotenv() and setup_logging() here ensures env vars are ready and logging
is configured before FastAPI router modules or pydantic-settings evaluate.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=str(_env_path))

from app.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)
