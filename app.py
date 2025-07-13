import os
import uuid
import json
from threading import Thread, Lock
from contextlib import asynccontextmanager
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import pipeline
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
#--- Pydantic models for data validation ---
#these classes define the expected format for API's input and output
#FastAPI uses them to automatically validate requests, parse data, and generate documentation

#defines the structure for a POST request to /translate
class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The text to be translated")
    target_language: str = Field(..., min_length=1, description="The full name of the target language")

class JobResponse(BaseModel):
    message: str
    request_id: str

#defines structure for the response when fetching a result
class Result(BaseModel):
    status: str
    result: str | None = None #string could be None is still proccessing

HELSINKI_NAME_TEMPLATE = "Helsinki-NLP/opus-mt-en-{lang_code}"
#mapping full language names to the required 2-letter codes
LANGUAGE_CODES = {
    "french": "fr",
    "spanish": "es",
    "chinese": "zh",
    "hindi": "hi",
    "arabic": "ar"
}

#--- Hugging Face Model Caching ---
#loading models is slow so load them once and then store in this dict
model_cache = {}
#prevents two requests from loading the same model at the same time
model_cache_lock = Lock()

#function loads a specific translation model
def get_translation_pipeline(target_language: str):
    lang_code = LANGUAGE_CODES.get(target_language.lower())

    if not lang_code:
        return None, f"Language '{target_language}' not supported."

    model_name = HELSINKI_NAME_TEMPLATE.format(lang_code=lang_code)
    cache_key = model_name

    with model_cache_lock:
        if cache_key in model_cache:
            return model_cache[cache_key], None

        logger.info(f"Loading model for cache key: {cache_key}...")
        try:
            translator = pipeline('translation', model=model_name)

            model_cache[cache_key] = translator 
            logger.info(f"Model {cache_key} loaded and cached successfully")
            return translator, None
        #keep for now, but might not be needed later -> negative cacheing
        except Exception as e:
            error_message = f"Failed to load model {cache_key}: {e}"
            logger.error(error_message)
            model_cache[cache_key] = None
            return None, error_message

#--- Redis Connection and Background Worker ---
#error detection for programs first boot up
redis_client = None
try:
    #application setup
    #redis connection
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))

    #create object that will handle all the communication with Redis
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    #attempts to reach Redis and get a response
    redis_client.ping()
    logger.info("Successfully connect to Redis!")

except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    redis_client = None

#define redis keys
REQUEST_QUEUE_KEY = "translation_request_queue"
RESULTS_CACHE_PREFIX = "translation_result:"

#runs continuously in a background thread to process jobs
def translation_worker():
    if not redis_client: return
    while True:
        #waits for job to appear in queue
        _, task_json = redis_client.blpop(REQUEST_QUEUE_KEY)
        task = json.loads(task_json) #parse the job data
        task_id = task['id']
        result_key = f"{RESULTS_CACHE_PREFIX}{task_id}"
        try:
            translator_pipeline, error = get_translation_pipeline(task['lang'])

            if translator_pipeline:
                result = translator_pipeline(task['text'])
                translated_text = result[0]['translation_text']
                status = 'completed'
            else:
                translated_text = error or "An unknown error occurred during model loading."
                status = 'failed'
        except Exception as e:
            logger.error(f"Error translating text for task {task_id}: {e}")
            translated_text = "An unexpected error occurred during translation."
            status = 'failed'

        #store final result back in Redis
        final_payload = json.dumps({'status': status, 'result': translated_text})
        redis_client.set(result_key, final_payload)

#--- FastAPI Application and Lifespan Manager ---
#manages startup and shutdown events for the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    if redis_client:
        worker_thread = Thread(target=translation_worker, daemon=True)
        worker_thread.start()
        logger.info("Translation worker started.")
    else:
        logger.warning("WARNING: Redis not connected. Translation worker not started.")
    yield #application runs here
    logger.info("Application shutdown.")

#create the main FastAPI
app = FastAPI(
    title="Efficient Asynchronous Translation Service",
    description="An API for high-performance translation using optimized Hugging Face models.",
    version="4.0.0",
    lifespan=lifespan
)

#--- API Endpoints ---

#accepts a translation request and queues it for a background worker
@app.post('/translate', response_model=JobResponse, status_code=202)
async def submit_translation(translation_request: TranslationRequest):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Service Unavailable: Cannot Connect to Redis.")
    
    #generate unique ID for this specific request
    request_id = str(uuid.uuid4())

    #dictionary to hold all information for this translation job
    task = {
        'id': request_id,
        'text': translation_request.text,
        'lang': translation_request.target_language,
     }

    result_key = f"{RESULTS_CACHE_PREFIX}{request_id}"

    #set an intial status so user and see their job in the queue
    initial_payload = json.dumps({'status': 'queued', 'result': None})
    redis_client.set(result_key, initial_payload)

    #push the job to the worker queue
    #rpush adds job to the end of the list -> creating a queue
    redis_client.rpush(REQUEST_QUEUE_KEY, json.dumps(task))
    return JobResponse(message="Request accepted.", request_id=request_id)

#Retrieves the result of a translation job by its ID
@app.get("/result/{request_id}", response_model=Result)
async def get_translation_result(request_id: str):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Service Unavailable: Cannot connect to Redis.")
    result_key = f"{RESULTS_CACHE_PREFIX}{request_id}"
    result_json = redis_client.get(result_key)
    if not result_json:
        raise HTTPException(status_code=404, detail="Request ID not found.")
    result = json.loads(result_json)
    # To save space, we delete the result from the cache after it's been retrieved
    if result.get('status') in ['completed', 'failed']:
        redis_client.delete(result_key)
    return Result(**result)

#function runs when we access https://localhost:5000/health
#its purpose is to report the status of the application
@app.get('/health', tags=['Monitoring'])
async def health_check():
    redis_status = 'unavailable'
    #check connection of redis_client
    if redis_client and redis_client.ping():
        redis_status = 'ok'
    else:
        raise HTTPException(status_code=503, detail="Service Unavailable: Cannot connect to Redis.")
    return {"api_status": "ok", "redis_status": "ok"}
