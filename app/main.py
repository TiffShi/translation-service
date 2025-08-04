import logging
import redis
from threading import Thread
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.endpoints import router as api_router
from app.db.redis_client import redis_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#--- FastAPI Application and Lifespan Manager ---
# manages startup and shutdown events for the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    #verifies the connection for the client created in db.py
    try:
        redis_client.ping()
        logger.info("Successfully connected to Redis!")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis: {e}. The worker will not be started.")

    yield #application runs here

    logger.info("Web server shutdown.")

# --- FastAPI App Instance ---

# Create the main FastAPI application instance.
app = FastAPI(
    title="Translation Microservice",
    description="An API for high-performance, lightweight text translation",
    version="3.0.0",
    lifespan=lifespan
)

# --- Router Inclusion ---
#attach the router from 'api/views.py' to the main application
#all routes defined in the router will be prepended with '/api'
app.include_router(api_router, prefix="/api")