import os
import time
import pytest
import json
import statistics
import requests
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- Test Configuration ---
BASE_URL = "http://localhost:8005/api"
#TARGET_LANGUAGES = ["Spanish", "French", "Arabic", "Hindi", "Chinese"]
TARGET_LANGUAGES = ["Spanish"]
TERMS_TO_TEST = [
    "recommended_treatment: Adjuvant vaginal brachytherapy with consideration of external beam radiation therapy per NCCN Stage IA grade 3 guidelines",
    "patient_notes: Your surgery removed the uterine cancer, which was limited to the inner half of the uterine muscle and did not spread to your lymph nodes. This is considered an early stage (IA) cancer. Based on guidelines, additional treatment may be recommended to reduce the risk of recurrence, and your care team will discuss options such as radiation therapy. We will work together to plan the next steps for your care.",
    "recommended_treatment: Observation",
    "patient_notes: Your report shows a low-grade endometrial cancer confined to the uterine lining with no spread to lymph nodes. No further treatment beyond your surgery is typically necessary. We recommend close monitoring with regular follow-up appointments.",
    "recommended_treatment: Observation or vaginal brachytherapy",
    "patient_notes: Your report shows a grade 2 endometrial cancer confined to the upper wall of the uterus with no lymph node spread. You have had surgery to remove the uterus and ovaries with no remaining cancer. Given the low stage, we will monitor you closely and may recommend a small internal vaginal radiation treatment to lower the chance of recurrence. Follow-up visits and imaging will be scheduled regularly.",
    # r"recommended_treatment: Systemic therapy \u00b1 EBRT \u00b1 vaginal brachytherapy",
    # "patient_notes: Your surgery showed endometrial cancer that invaded the uterine muscle less than halfway, spread to the cervix and an ovary, but did not involve the lymph nodes. This is classified as stage IIIA. The recommended treatment includes chemotherapy and may include focused radiation to the pelvis or vaginal area. We will guide you through each step and provide support throughout your treatment.",
    # "recommended_treatment: Systemic therapy with or without external beam radiation therapy and/or vaginal brachytherapy",
    # "patient_notes: The pathology report shows a high-grade uterine serous carcinoma removed by hysterectomy with focal superficial myometrial invasion and no nodal or distant disease. Based on NCCN guidelines for high-risk histology Stage IA uterine serous carcinoma, adjuvant systemic chemotherapy with or without vaginal brachytherapy is recommended to reduce recurrence risk.",
    # r"recommended_treatment: Systemic therapy \u00b1 EBRT \u00b1 vaginal brachytherapy",
    # "patient_notes: Your pathology shows a high-grade uterine cancer that has reached the outer lining of the uterus but has not spread to lymph nodes. We recommend a combination of chemotherapy and pelvic radiation, which may include internal vaginal radiation, to reduce the risk of the cancer returning.",
    # "recommended_treatment: Total hysterectomy and bilateral salpingo-oophorectomy with surgical staging followed by carboplatin and paclitaxel chemotherapy plus external beam pelvic radiation and vaginal brachytherapy",
    # "patient_notes: This report shows uterine serous carcinoma with spread to pelvic, common iliac, and para-aortic lymph nodes. Your uterus, ovaries, and fallopian tubes were removed, and no cancer was found in the ovaries or omentum. To lower the chance of recurrence, you will receive carboplatin and paclitaxel chemotherapy combined with external beam pelvic radiation and a vaginal brachytherapy boost. We will support you through each step of this treatment plan.",
    # "recommended_treatment: Total hysterectomy with bilateral salpingo-oophorectomy and surgical staging followed by adjuvant carboplatin-paclitaxel chemotherapy and vaginal brachytherapy",
    # "patient_notes: Your pathology report shows a high-grade uterine cancer that has invaded most of the muscle layer but has not spread to your lymph nodes. We recommend removing the uterus and ovaries with surgical staging, followed by chemotherapy and focused radiation to the vaginal area to reduce recurrence risk.",
    # "recommended_treatment: Adjuvant pelvic external beam radiation therapy with vaginal brachytherapy and systemic chemotherapy",
    # "patient_notes: Your diagnosis is endometrial cancer that was removed by surgery and found to have invaded more than half of the uterine muscle but did not spread to lymph nodes. To lower the chance of return, we recommend targeted radiation to your pelvis and vagina and a course of chemotherapy. This combined approach is standard for your stage of disease and is aimed at improving long-term outcomes.",
    # "recommended_treatment: Systemic therapy plus external beam pelvic radiotherapy and vaginal brachytherapy",
    # "patient_notes: Your pathology shows a high-grade uterine cancer that has spread to lymph nodes. The cancer invaded less than half of the uterine muscle but metastasized to several lymph nodes. The recommended plan includes chemotherapy along with targeted radiation to the pelvis and possibly a small internal radiation treatment. Your care team will discuss this combined approach to help reduce the risk of recurrence."
]
SIMILARITY_THRESHOLD = 0.85
#default value
total_duration = 0

# --- OpenAI Setup ---
openai_api_key = os.environ.get("OPENAI_API_KEY")
skip_if_no_key = pytest.mark.skipif(not openai_api_key, reason="OPENAI_API_KEY environment variable not set")

# --- Sentence Transformer Model ---
embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

#takes our text and sends it to the OpenAI API to get a high-quality translation to compare against
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
        print(f"Warning: OpenAI API call failed for '{text}': {e}")
        return "N/A"

#--- Main Test Function ---
#This test measure the performace and quality of a batch of translation requests for a specific language
@pytest.mark.parametrize("target_language", TARGET_LANGUAGES)
@skip_if_no_key
def test_batch(target_language):
    #submit all translation jobs for the current language
    print(f"--- Starting Benchmark for: {target_language.upper()} ---")
    print(f"Submitting {len(TERMS_TO_TEST)} translation requests...")
    #will only hold jobs we need to poll for (status 202)
    request_map = {}
    #will hold results we get immediatley from the cache (status 200)
    completed_results = []
    start_time = time.time()

    for term in TERMS_TO_TEST:
        try:
            submit_response = requests.post (
                f"{BASE_URL}/translate",
                json={"text": term, "target_language": target_language}
            )
            #assert checks if condition is true. If not, test fails
            assert submit_response.status_code in [200, 202] #check if request accepted

            #if it was a new json, add it to map to be polled later
            if submit_response.status_code == 202:
                request_id = submit_response.json()["request_id"]
                request_map[request_id] = {"original": term }

            elif submit_response.status_code == 200:
                print(f"Cache hit for term: '{term[:30]}'...")
                completed_results.append({
                    "original": term,
                    "status": "completed",
                    "service_translation": submit_response.json()["result"]
                })

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to submit request for '{term}': {e}")

    #poll for results of background jobs
    if request_map:
        print(f"{len(request_map)} jobs for {target_language} submitted for background processing.")
        print("Waiting for all translations to complete...")
        pending_ids = set(request_map.keys())
        timeout_seconds = 300

        while pending_ids and (time.time() - start_time) < timeout_seconds:
            for req_id in list(pending_ids):
                try:
                    result_response = requests.get(f"{BASE_URL}/result/{req_id}")
                    #check if the /result endpoint is working
                    if result_response.status_code == 200:
                        result_data = result_response.json()

                        if result_data.get("status") in ["completed", "failed"]:
                            request_map[req_id]['status'] = result_data.get("status")
                            request_map[req_id]['service_translation'] = result_data.get("result")
                            pending_ids.remove(req_id)
                except requests.exceptions.RequestException as e:
                    print(f"Warning: Could not poll for request ID {req_id}: {e}")

            time.sleep(1)
        assert len(pending_ids) == 0, f"Test timed out. {len(pending_ids)} jobs did not complete for {target_language}."

    end_time = time.time()

    #fetch OpenAI translations and calculate quality scores
    print("All jobs completed.")
    print("Fetching reference translations from OpenAI and calculating quality...")
    
    for data in request_map.values():
        completed_results.append(data)

    openai_client = OpenAI(api_key=openai_api_key)
    similarity_scores = []
    current_language_results = []

    for data in completed_results:
        result_entry = {"Original Term": data.get('original', 'N/A')}
        if data.get('status') == 'completed':
            original_text = data['original']
            service_translation = data['service_translation']
            openai_translation = get_openai_translation(openai_client, original_text, target_language)

            result_entry["Service Translation"] = service_translation
            result_entry["OpenAI Translation"] = openai_translation

            #check if OpenAI call was successful
            if openai_translation != "N/A":
                #compare the results using embeddings
                service_embedding = embedding_model.encode([service_translation])
                openai_embedding = embedding_model.encode([openai_translation])
                score = cosine_similarity(service_embedding, openai_embedding)[0][0]
                similarity_scores.append(score)
                result_entry["Similarity Score"] = f"{score:.4f}"
        else:
            result_entry["Service Translation"] = data.get('service_translation', 'SERVICE FAILED')
            result_entry["OpenAI Translation"] = "N/A"
            result_entry["Similarity Score"] = "N/A"

        current_language_results.append(result_entry)

    #read existing json, update it, and write back
    output_filename = "analysis2.json"
    all_results = {}

    #try to load existing results from the file
    if os.path.isfile(output_filename):
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not decode JSON from {output_filename}. Starting fresh.")

    all_results[target_language] = current_language_results

    print(f"Writing/updating results for {target_language} in {output_filename}...")
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)

    num_completed = len(request_map)
    num_phrases = len(TERMS_TO_TEST)
    total_duration = end_time - start_time

    print(f"\n--- BATCH REPORT FOR: {target_language.upper()} ---")
    print(f"Total phrases submitted: {num_phrases}")
    print(f"Total phrases completed: {num_completed}")
    print(f"Total time taken: {total_duration:.2f} seconds")
    if num_completed > 0:
        avg_time = total_duration / num_completed
        print(f"Average time per phrase: {avg_time:.2f} seconds")
    if similarity_scores:
        avg_similarity = statistics.mean(similarity_scores)
        print(f"Average Similarity Score: {avg_similarity:.4f}")
    print(f"Detailed results for {target_language} saved to: {output_filename}")
    print("--- END REPORT ---\n")
