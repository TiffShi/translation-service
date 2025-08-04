import logging
from app.services.translation_engine import get_translation_pipeline
from app.core.config import LANGUAGE_CODES

# --- Gunicorn Settings ---
bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"

logger = logging.getLogger(__name__)

# -- Server Hooks ---
#this gunicorn hook runs in each worker process after it has been forked
#this is a safe place to pre-load models for the web server if needed
def post_fork(server, worker):
    logger.info(f"Gunicorn worker {worker.pid} started.")
