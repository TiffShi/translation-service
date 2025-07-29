import redis
from translation_service.config import REDIS_HOST, REDIS_PORT

# This creates the client object. The actual connection and verification
# will happen in the main application's startup sequence.
# This object is now a singleton that can be imported anywhere.
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
