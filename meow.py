# import os
# import uuid
# import json
# from threading import Thread, Lock
# from contextlib import asynccontextmanager
# import redis
# from fastapi import FastAPI, HTTPException, Response, Depends, status
# from pydantic import BaseModel, Field
# from transformers import pipeline
# import logging
# import torch
# import time
# import hashlib
# from auth import verify_token

# #used to control CPU usage
# os.environ["TOKENIZERS_PARALLELISM"] = "false"
# torch.set_num_threads(1)

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# #--- Pydantic models for data validation ---
# #these classes define the expected format for API's input and output
# #FastAPI uses them to automatically validate requests, parse data, and generate documentation
# #defines the structure for a POST request to /translate
# class TranslationRequest(BaseModel):
#     text: str = Field(..., min_length=1, description="The text to be translated")
#     target_language: str = Field(..., min_length=1, description="The full name of the target language")

# class TranslationResponse(BaseModel):
#     message: str
#     result: str
#     from_cache: bool = True

# class JobResponse(BaseModel):
#     message: str
#     request_id: str

# #defines structure for the response when fetching a result
# class Result(BaseModel):
#     status: str
#     result: str | None = None #string could be None is still proccessing

# HELSINKI_NAME_TEMPLATE = "Helsinki-NLP/opus-mt-en-{lang_code}"
# #mapping full language names to the required 2-letter codes
# LANGUAGE_CODES = {
#     "french": "fr",
#     "spanish": "es",
#     "chinese": "zh",
#     "hindi": "hi",
#     "arabic": "ar"
# }

# #--- Hugging Face Model Caching ---
# #loading models is slow so load them once and then store in this dict
# model_cache = {}
# #prevents two requests from loading the same model at the same time
# model_cache_lock = Lock()

# #generates a consistent, unique cache key for a translation
# def get_translation_cache_key(text: str, lang: str):
#     key_string = f"{text}:{lang}".encode('utf-8')
#     key_hash = hashlib.sha256(key_string).hexdigest()
#     return f"{TRANSLATION_CACHE_PREFIX}{key_hash}"

# #function loads a specific translation model
# def get_translation_pipeline(target_language: str):
#     lang_code = LANGUAGE_CODES.get(target_language.lower())

#     if not lang_code:
#         return None, f"Language '{target_language}' not supported."

#     model_name = HELSINKI_NAME_TEMPLATE.format(lang_code=lang_code)
#     cache_key = model_name

#     with model_cache_lock:
#         if cache_key in model_cache:
#             return model_cache[cache_key], None

#         logger.info(f"Loading model for cache key: {cache_key}...")
#         try:
#             translator = pipeline('translation', model=model_name)

#             model_cache[cache_key] = translator
#             logger.info(f"Model {cache_key} loaded and cached successfully")
#             return translator, None
#         except Exception as e:
#             error_message = f"Failed to load model {cache_key}: {e}"
#             logger.error(error_message)
#             return None, error_message

# #--- Redis Connection and Background Worker ---
# #error detection for programs first boot up
# redis_client = None
# try:
#     #application setup
#     #redis connection
#     redis_host = os.environ.get('REDIS_HOST', 'localhost')
#     redis_port = int(os.environ.get('REDIS_PORT', 6379))

#     #create object that will handle all the communication with Redis
#     redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

#     #attempts to reach Redis and get a response
#     redis_client.ping()
#     logger.info("Successfully connect to Redis!")

# except redis.exceptions.ConnectionError as e:
#     logger.error(f"Could not connect to Redis: {e}")
#     redis_client = None

# #define redis keys
# REQUEST_QUEUE_KEY = "translation_request_queue"
# RESULTS_CACHE_PREFIX = "translation_result:"
# TRANSLATION_CACHE_PREFIX = "translation_cache:"

# #runs continuously in a background thread to process jobs
# def translation_worker():
#     if not redis_client: return

#     BATCH_SIZE = 8
#     BATCH_TIMEOUT = 1.0 #seconds

#     while True:
#         jobs_to_process = []
#         while len(jobs_to_process) < BATCH_SIZE:
#             try:
#                 task_json = redis_client.rpop(REQUEST_QUEUE_KEY)
#                 #if queue is empty
#                 if not task_json:
#                     break

#                 jobs_to_process.append(json.loads(task_json))

#             except Exception as e:
#                 logger.error(f"Error popping job from Redis: {e}")
#                 break
        
#         if not jobs_to_process:
#             #if the queue was empty, wait a moment before checking again.
#             time.sleep(BATCH_TIMEOUT)
#             continue

#         logger.info(f"Processing a batch of {len(jobs_to_process)} jobs.")
#         #group by languages
#         #we can only batch translate texts that are for the same language model
#         grouped_by_lang = {}
#         for job in jobs_to_process:
#             lang = job['lang']
#             if lang not in grouped_by_lang:
#                 grouped_by_lang[lang] = []
#             grouped_by_lang[lang].append(job)

#         #process each language group as a batch
#         for lang, jobs in grouped_by_lang.items():
#             translator_pipeline, error = get_translation_pipeline(lang)

#             #if the model failed to load, mark all jobs for this language as failed
#             if not translator_pipeline:
#                 for job in jobs:
#                     job['status'] = 'failed'
#                     job['result'] = error
#                 continue

#             try:
#                 #create a list of just the text to be translated.
#                 texts = [job['text'] for job in jobs]

#                 start_time = time.perf_counter()
#                 #translate the entire batch in one call
#                 translated_results = translator_pipeline(texts)

#                 duration = time.perf_counter() - start_time

#                 logger.info(f"Translated batch for {lang} ({len(jobs)} jobs) in {duration:.4f} seconds.")

#                 #map the results back to their original jobs.
#                 for i, job in enumerate(jobs):
#                     job['status'] = 'completed'
#                     job['result'] = translated_results[i]['translation_text']
#             except Exception as e:
#                 logger.error(f"Error during batch translation for language {lang}: {e}")
#                 for job in jobs:
#                     job['status'] = 'failed'
#                     job['result'] = "Error during batch processing."

#         # --- Save all results back to Redis ---
#         try:
#             with redis_client.pipeline() as pipe:
#                 for job in jobs_to_process:
#                     #save to translation cache
#                     if job.get('status') == 'completed':
#                         final_cache_key = get_translation_cache_key(job['text'], job['lang'])
#                         #ex = how many seconds the cache will keep the translation
#                         pipe.set(final_cache_key, job['result'], ex=300)
                    
#                     #save job status for client pickup
#                     result_key = f"{RESULTS_CACHE_PREFIX}{job['id']}"
#                     final_payload = json.dumps({'status': job['status'], 'result': job['result']})
#                     pipe.set(result_key, final_payload)
                
#                 pipe.execute()
#             logger.info(f"Successfully saved results for {len(jobs_to_process)} jobs to Redis.")
#         except Exception as e:
#             logger.error(f"Error saving results to Redis: {e}")

# #--- FastAPI Application and Lifespan Manager ---
# #manages startup and shutdown events for the application
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger.info("Application startup...")
#     if redis_client:
#         logger.info("Pre-loading all supported translation models")
#         for lang_name in LANGUAGE_CODES.keys():
#             get_translation_pipeline(lang_name)
#         logger.info("All models loaded and ready.")

#         worker_thread = Thread(target=translation_worker, daemon=True)
#         worker_thread.start()
#         logger.info("Translation worker started.")
#     else:
#         logger.warning("WARNING: Redis not connected. Translation worker not started.")
#     yield #application runs here
#     logger.info("Application shutdown.")

# #create the main FastAPI
# app = FastAPI(
#     title="Efficient Asynchronous Translation Service",
#     description="An API for high-performance translation using Helsinki-NLP MarianMT Models.",
#     version="4.0.0",
#     lifespan=lifespan
# )

# #--- API Endpoints ---

# #accepts a translation request and queues it for a background worker
# @app.post('/translate', response_model=JobResponse | TranslationResponse, dependencies=[Depends(verify_token)])
# async def submit_translation(translation_request: TranslationRequest, response: Response):
#     if not redis_client:
#         raise HTTPException(status_code=503, detail="Service Unavailable: Cannot Connect to Redis.")

#     #check for a cached translation
#     final_cache_key = get_translation_cache_key(translation_request.text, translation_request.target_language)

#     cached_result = redis_client.get(final_cache_key)

#     if cached_result:
#         logger.info(f"Cache hit for key: {final_cache_key}")
#         return TranslationResponse(
#             message="Translation retrived from cache.",
#             result=cached_result
#         )

#     logger.info(f"Cache miss for key: {final_cache_key}. Submitting new job.")
#     #generate unique ID for this specific request
#     request_id = str(uuid.uuid4())

#     #dictionary to hold all information for this translation job
#     task = {
#         'id': request_id,
#         'text': translation_request.text,
#         'lang': translation_request.target_language,
#      }

#     result_key = f"{RESULTS_CACHE_PREFIX}{request_id}"

#     #set an intial status so user and see their job in the queue
#     initial_payload = json.dumps({'status': 'queued', 'result': None})
#     redis_client.set(result_key, initial_payload)

#     #push the job to the worker queue
#     #rpush adds job to the end of the list -> creating a queue
#     redis_client.rpush(REQUEST_QUEUE_KEY, json.dumps(task))
#     response.status_code = 202
#     return JobResponse(message="Request accepted.", request_id=request_id)

# #Retrieves the result of a translation job by its ID
# @app.get("/result/{request_id}", response_model=Result, dependencies=[Depends(verify_token)])
# async def get_translation_result(request_id: str):
#     if not redis_client:
#         raise HTTPException(status_code=503, detail="Service Unavailable: Cannot connect to Redis.")

#     result_key = f"{RESULTS_CACHE_PREFIX}{request_id}"
#     result_json = redis_client.get(result_key)

#     if not result_json:
#         raise HTTPException(status_code=404, detail="Request ID not found.")

#     result = json.loads(result_json)

#     #if job is done, set TTL for 5 minutes
#     if result.get('status') in ['completed', 'failed']:
#         redis_client.expire(result_key, 300)

#     return Result(**result)

# #function runs when we access https://localhost:5000/health
# #its purpose is to report the status of the application
# @app.get('/health', tags=['Monitoring'])
# async def health_check():
#     redis_status = 'unavailable'

#     #check connection of redis_client
#     if redis_client and redis_client.ping():
#         redis_status = 'ok'
#     else:
#         raise HTTPException(status_code=503, detail="Service Unavailable: Cannot connect to Redis.")

#     return {"api_status": "ok", "redis_status": "ok"}