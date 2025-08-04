import os
import json
os.environ['SERVICE_TOKEN_SECRET'] = 'test-secret-value'

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

#this client allows you to make "fake" requests to your app for testing purposes
client = TestClient(app)

# --- Test Suite ---

#tests the /health endpoint when Redis connection is sucessful
def test_health_check_sucess():
    #patch redis_client.ping() to simulate a successful connection
    with patch('app.api.endpoints.redis_client') as mock_redis:
        mock_redis.ping.return_value = True

        #make request to the health endpoint
        response = client.get("/api/health")

        assert response.status_code == 200 #request sucessful
        assert response.json() == {"api_status": "ok", "redis_status": "ok"}

#tests the /health endpoint when Redis connection fails
def test_health_check_redis_failure():
    #patch redis_client.ping() to simulate a failed connection
    with patch('app.api.endpoints.redis_client') as mock_redis:
        mock_redis.ping.return_value = False
        response = client.get("/api/health")

        assert response.status_code == 503 #service unavailable error
        assert response.json() == {"detail": "Service Unavailable: Cannot connect to Redis."}

#tests the POST /translate endpoint when a translation is found in the cache
@patch('app.api.endpoints.redis_client', new_callable=MagicMock)
def test_translate_cache_hit(mock_redis):
    #configure mock to simulate a cache hit
    cached_translation = "Ceci est un test"
    #the 'get' method should return a translated string
    mock_redis.get.return_value = cached_translation
    
    #make a request to the endpoint
    response = client.post(
        "/api/translate",
        json={"text": "This is a test", "target_language": "french"}
    )

    #check for expected response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"] == cached_translation
    assert data["from_cache"] is True

    #assert 'rpush' method (for queueing a new job) was NOT called
    mock_redis.rpush.assert_not_called()

#tests the POST /translation endpoint when a translation is NOT in the cache
@patch('app.api.endpoints.redis_client', new_callable=MagicMock)
def test_translate_cache_miss(mock_redis):
    #Configure the mock to simulate a cache miss
    mock_redis.get.return_value = None

    #make request to the endpoint
    response = client.post(
        "/api/translate",
        json={"text": "This is a new test", "target_language": "spanish"}
    )

    #check if response indicates new job was accepted
    assert response.status_code == 202
    data = response.json()
    assert data["message"] == "Request accepted."
    assert "request_id" in data #check that a request ID was returned

    #assert that 'set' and 'rpush' methods were called to queue the job
    mock_redis.set.assert_called_once()
    mock_redis.rpush.assert_called_once()

#test the GET /result/{request_id} endpoint for a completed job
def test_get_result_completed():
    request_id = "test-id-123"
    job_result = {
        "status": "completed",
        "result": "Este es un resultado"
    }

    with patch('app.api.endpoints.redis_client') as mock_redis:
        #arrange mock reddis to return the JSON string of the completed job
        mock_redis.get.return_value = json.dumps(job_result)

        #make the request
        response = client.get(f"/api/result/{request_id}")

        #check response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == "Este es un resultado"
        assert data["from_cache"] is False #should default to False

#tests the GET /result/{request_id} endpoint for an ID that doesn't exist
def test_get_result_not_found():
    request_id = "non-existent-id"
    with patch('app.api.endpoints.redis_client') as mock_redis:
        #arrange mock Redis to return None, as if key doesn't exist
        mock_redis.get.return_value = None

        #make the request
        response = client.get(f"/api/result/{request_id}")

        assert response.status_code == 404 # not found error
        assert response.json() == {"detail": "Request ID not found."}

#tests the GET /request/{request_id} endpoint for a job that is still in progress
def test_get_result_still_queued():
    request_id = "queued-id-456"
    job_result = {
        "status": "queued",
        "result": None
    }

    with patch('app.api.endpoints.redis_client') as mock_redis:
        #arrange mock Redis to return the JSON of the queued job
        mock_redis.get.return_value = json.dumps(job_result)

        #make the request
        response = client.get(f"/api/result/{request_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["result"] is None
