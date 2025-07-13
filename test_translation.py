import os
import time
import pytest
import requests
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- Test Configuration ---
BASE_URL = "http://localhost:5000"
TEST_TEXT = "Adjuvant vaginal brachytherapy with consideration of external beam radiation therapy per NCCN Stage IA grade 3 guidelines"
TARGET_LANGUAGE_NAME = "Spanish"
SIMILARITY_THRESHOLD = 0.8

# --- OpenAI Setup ---
openai_api_key = os.environ.get("OPENAI_API_KEY")
skip_if_no_key = pytest.mark.skipif(not openai_api_key, reason="OPENAI_API_KEY environment variable not set")

# --- Sentence Transformer Model ---
embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

#creates an OpenAI client that can be reused across multiple tests in this file
@pytest.fixture(scope="module")
def openai_client():
    if openai_api_key:
        return OpenAI(api_key=openai_api_key)
    return None

#takes our text and sends it to the OpenAI API to get a high-quality
#translation to compare against
def get_openai_translation(client, text, language_name) :
    if not client:
        return "OpenAI client not available"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the user's text to {language_name}."},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        pytest.fail(f"OpenAI API call failed: {e}")

#--- Main Test Function ---
@skip_if_no_key
def test_lang_comparison():
    #submit job to our service
    print(f"Submitting translation request for: '{TEST_TEXT}'")
    start_time = time.time()
    submit_response = requests.post (
        f"{BASE_URL}/translate",
        json={"text": TEST_TEXT, "target_language": TARGET_LANGUAGE_NAME}
    )   
    #assert checks if condition is true. If not, test fails
    assert submit_response.status_code == 202 #check if request accepted
    data = submit_response.json()
    assert "request_id" in data 
    request_id = data["request_id"]
    print(f"Request submitted successfully. ID: {request_id}")

    #poll for the result
    service_translation = ""
    for i in range(1000):
        print("Polling for result... ")
        result_response = requests.get(f"{BASE_URL}/result/{request_id}")
        assert result_response.status_code == 200 #check if the /result endpoint is working
        result_data = result_response.json()
        if result_data.get("status") == "completed":
            end_time = time.time()
            service_translation = result_data.get("result")
            duration = end_time - start_time
            print(f"Your service took {duration:.2f} seconds to complete the translation")
            break
        time.sleep(1) #wait 1 second before polling again
    
    assert service_translation, "Translation from service was not completed in time."
    
    #get reference translation from OpenAI
    print("Fetching translation from OpenAI...")
    openai_client_instance = OpenAI(api_key=openai_api_key)
    openai_translation = get_openai_translation(openai_client_instance, TEST_TEXT, TARGET_LANGUAGE_NAME)

    #compare the results using embeddings
    print("Generating embeddings for comparison...")
    service_embedding = embedding_model.encode([service_translation])
    openai_embedding = embedding_model.encode([openai_translation])
    #calculate the cosine similarity score between two vectors
    similarity_score = cosine_similarity(service_embedding, openai_embedding)[0][0]

    # Print a clear report for the user to see the comparison.
    print("\n--- SEMANTIC COMPARISON ---")
    print(f"Original Text: {TEST_TEXT}")
    print(f"Target Language: {TARGET_LANGUAGE_NAME}")
    print("-" * 20)
    print(f"Your Service Result:  '{service_translation}'")
    print(f"OpenAI gpt-4o Result: '{openai_translation}'")
    print("-" * 20)
    print(f"Cosine Similarity Score: {similarity_score:.4f}")
    print(f"Required Threshold: > {SIMILARITY_THRESHOLD}")
    print("--- END COMPARISON ---\n")

    assert similarity_score > SIMILARITY_THRESHOLD, \
        f"Translations are not semantically similar enough. Score: {similarity_score}"
