from pydantic import BaseModel

class TranscriptSegment(BaseModel):
    text: str
    start_time: float
    end_time: float

class TranscriptionResponse(BaseModel):
    filename: str
    segments: list[TranscriptSegment]
