# High-Performance Translation Microservice

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A robust, scalable, and production-ready microservice for high-performance text translation using an asynchronous architecture.

## Architecture

The system is composed of three core services that run in separate Docker containers:

1.  **FastAPI App (Web Server):** A lightweight API server that handles all incoming HTTP requests. Its only jobs are to validate requests, check for cached results, and queue new translation jobs.
2.  **Redis (Message Broker & Cache):** A high-performance in-memory database that serves two critical roles:
    * **Message Queue:** Holds the list of pending translation jobs for the workers.
    * **Cache:** Stores the results of completed translations for fast retrieval, reducing redundant processing.
3.  **Translator Worker:** A background process that pulls jobs from the Redis queue, loads the appropriate Hugging Face models, performs the translation, and stores the result back in Redis. This service can be scaled horizontally to increase processing throughput.

```
+-----------------+      +----------------+      +--------------------+
|                 |      |                |      |                    |
|   User/Client   |----->|  FastAPI App   |----->|   Redis (Queue)    |
|                 |      |  (Web Server)  |      |                    |
+-----------------+      +-------+--------+      +---------+----------+
                                 |                          |
                                 | (Cache Check)            | (Pop Job)
                                 |                          |
                                 v                          v
                           +-----+-----+            +-------+--------+
                           |           |            |                |
                           |   Redis   |<-----------| Translator     |
                           |  (Cache)  |  (Save     | Worker         |
                           |           |   Result)  | (ML Inference) |
                           +-----------+            +----------------+
```

## Key Features

* **Asynchronous API:** Immediately accepts requests and returns a job ID, allowing clients to poll for results without long-running HTTP connections.
* **Decoupled & Scalable Workers:** The web server and workers are separate services, allowing the number of workers to be scaled up or down based on the translation workload.
* **Efficient Batch Processing:** The worker intelligently groups jobs by language to maximize the throughput of the underlying Hugging Face models.
* **Multi-Layer Caching:** Utilizes Redis to cache completed translations, providing instant responses for repeated requests.
* **Production-Ready:** Fully containerized with Docker and configured to run with a Gunicorn production server.
* **Comprehensive Testing:** Includes both unit/integration tests (`pytest`) and a full performance/quality benchmark suite.

## Tech Stack

* **Backend:** Python, FastAPI
* **ML Models:** Hugging Face Transformers (Helsinki-NLP)
* **Database / Broker:** Redis
* **Server:** Gunicorn, Uvicorn
* **Containerization:** Docker, Docker Compose
* **Testing:** Pytest, Requests, OpenAI (for benchmark comparison)

## Setup and Installation

### Prerequisites

* Docker and Docker Compose installed on your local machine.
* An OpenAI API key (for running the quality benchmark tests).

### 1. Clone the Repository

```bash
git clone https://github.com/TiffShi/translation-service.git
cd translation-service
```
### 2. Configure Environment Variables

The project uses an .env file to manage secrets and configuration.

First, copy the example file:

```bash
cp .env.example .env
```
Next, open the .env file and add your secrets:

```bash
# .env
# A unique, random string for internal service authentication
SERVICE_TOKEN_SECRET=your-new-super-secret-and-unique-value
# Your OpenAI API key (required for running the test_translation.py benchmark)
OPENAI_API_KEY=sk-your-openai-api-key-here
```
### 3. Build and Run the Services

Use Docker Compose to build the images and start all the services.

```bash
docker-compose up --build
```
### Usage

The best way to interact with the API is through the auto-generated interactive documentation.

* API Docs (Swagger UI): http://localhost:5000/docs

From this page, you can execute requests directly from your browser.

### Example using Curl:
**1\. Submit a new translation job:**

```bash
curl -X 'POST' \
  'http://localhost:5000/api/translate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Hello, world",
    "target_language": "french"
}
```
If this is a new job, you will get a response like this:

```bash
{
  "message": "Request accepted.",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```
**2\. Retrieve the result:**

```bash
curl -X 'GET' \
  'http://localhost:5000/api/result/a1b2c3d4-e5f6-7890-1234-567890abcdef' \
  -H 'accept: application/json'
```
Once completed, the response will look like this:

```bash
{
  "status": "completed",
  "result": "Bonjour, le monde",
  "from_cache": false
}
```

## Testing
**1. Unit & Integration Tests:**

```bash
pytest tests/test_api_endpoints.py
```

**2. Performance + Quality Benchmark:**

```bash
pytest tests/test_translation.py
```

**3. Both:**

```bash
pytest -v -s
```