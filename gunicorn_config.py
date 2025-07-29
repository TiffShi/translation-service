import logging
from services.translation import get_translation_pipeline
from translation_service.config import LANGUAGE_CODES

# --- Gunicorn Settings ---
bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"
