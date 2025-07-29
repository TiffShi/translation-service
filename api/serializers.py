from pydantic import BaseModel, Field

#--- Pydantic models for data validation ---
#these classes define the expected format for API's input and output
#FastAPI uses them to automatically validate requests, parse data, and generate documentation

#defines the structure for a POST request to /translate
class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The text to be translated")
    target_language: str = Field(..., min_length=1, description="The full name of the target language")

#defines the response when a translation is retrieved directly from the cache
class TranslationResponse(BaseModel):
    message: str
    result: str
    from_cache: bool = True

#defines the response when a new translation job is successfully submitted
class JobResponse(BaseModel):
    message: str
    request_id: str

#defines the structure for the response when fetching a job result
class Result(BaseModel):
    status: str
    result: str | None = None #string could be None if it is still proccessing