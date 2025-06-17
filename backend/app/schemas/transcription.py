from pydantic import BaseModel

class TranscriptionRequest(BaseModel):
    project_id: str

class TranscriptSegment(BaseModel):
    text: str
    start_time: float
    end_time: float

class TranscriptionResponse(BaseModel):
    filename: str
    segments: list[TranscriptSegment]
