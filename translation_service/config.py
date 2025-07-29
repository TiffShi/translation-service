import os
import torch

# --- Environment Setup ---
#controls CPU usage
os.environ["TOKENIZERS_PARALLELISM"] = "false"
#sets the number of threads for PyTorch to use
torch.set_num_threads(1)

# --- Model and Language Configuration ---
#template for constructing the names of the machine learning models
HELSINKI_NAME_TEMPLATE = "Helsinki-NLP/opus-mt-en-{lang_code}"
#mapping of full language names to the two-letter codes required by the models
LANGUAGE_CODES = {
    "french": "fr",
    "spanish": "es",
    "chinese": "zh",
    "hindi": "hi",
    "arabic": "ar"
}

# --- Redis Configuration ---
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
#name of the list in Redis that will be used as the job queue
REQUEST_QUEUE_KEY = "translation_request_queue"
#prefix for keys where job results are stored
RESULTS_CACHE_PREFIX = "translation_result:"
#prefix for keys where final, completed translations are cached for reuse
TRANSLATION_CACHE_PREFIX = "translation_cache:"

# --- Worker Configuration ---
#max number of jobs the worker will pull from the queue at one time
BATCH_SIZE = 8
#number of seconds the worker will wait for a new job before checking again
BATCH_TIMEOUT = 1.0

# --- Auth Configuration ---
#URL for the central auth service, which must be provided by an environment variable
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL")
#secret token for secure communication between this service and other internal services
SERVICE_TOKEN_SECRET = "db-service-secret-token"