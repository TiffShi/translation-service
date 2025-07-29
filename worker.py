import logging
import sys
from threading import Thread

sys.path.append('.')

from services.translation import translation_worker, get_translation_pipeline
from translation_service.config import LANGUAGE_CODES
from db import redis_client

NUM_WORKER_THREADS = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#pre-loads all the ML models into the shared memory for this process
#spawns multiple worker threads to process jobs concurrently
def main():
    logger.info("--- Starting Multi-Threaded Translation Worker Process ---")

    if not redis_client:
        logger.error("Could not connect to Redis. Worker cannot start.")
        return

    #pre-load model once into main thread
    #this model cache will be shared by all threads spawned in this process
    logger.info(f"Main process ({__name__}): Pre-loading all supported translation models...")
    for lang_name in LANGUAGE_CODES.keys():
        get_translation_pipeline(lang_name)
    logger.info(f"Main Process ({__name__}): All models loaded and ready to be shared.")

    #create and start worker threads
    threads = []
    for i in range(NUM_WORKER_THREADS):
        logger.info(f"Starting worker thread {i+1}/{NUM_WORKER_THREADS}...")
        thread = Thread(target=translation_worker, args=(redis_client,))
        thread.daemon = True
        threads.append(thread)
        thread.start()

    #keep the main process alive
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()