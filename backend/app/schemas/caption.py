from pydantic import BaseModel
from .transcription import TranscriptSegment

class CaptionFormatRequest(BaseModel):
    segments: list[TranscriptSegment]
    max_chars_per_line: int = 40
    max_lines_per_caption: int = 2

class CaptionFormatResponse(BaseModel):
    srt_content: str
