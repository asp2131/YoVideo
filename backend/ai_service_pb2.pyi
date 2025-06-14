from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TranscriptSegment(_message.Message):
    __slots__ = ("text", "start_time", "end_time")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    text: str
    start_time: float
    end_time: float
    def __init__(self, text: _Optional[str] = ..., start_time: _Optional[float] = ..., end_time: _Optional[float] = ...) -> None: ...

class TranscribeAudioRequest(_message.Message):
    __slots__ = ("audio_data", "original_filename")
    AUDIO_DATA_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_FILENAME_FIELD_NUMBER: _ClassVar[int]
    audio_data: bytes
    original_filename: str
    def __init__(self, audio_data: _Optional[bytes] = ..., original_filename: _Optional[str] = ...) -> None: ...

class TranscribeAudioResponse(_message.Message):
    __slots__ = ("filename", "segments")
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    SEGMENTS_FIELD_NUMBER: _ClassVar[int]
    filename: str
    segments: _containers.RepeatedCompositeFieldContainer[TranscriptSegment]
    def __init__(self, filename: _Optional[str] = ..., segments: _Optional[_Iterable[_Union[TranscriptSegment, _Mapping]]] = ...) -> None: ...

class FormatCaptionsRequest(_message.Message):
    __slots__ = ("segments", "max_chars_per_line", "max_lines_per_caption")
    SEGMENTS_FIELD_NUMBER: _ClassVar[int]
    MAX_CHARS_PER_LINE_FIELD_NUMBER: _ClassVar[int]
    MAX_LINES_PER_CAPTION_FIELD_NUMBER: _ClassVar[int]
    segments: _containers.RepeatedCompositeFieldContainer[TranscriptSegment]
    max_chars_per_line: int
    max_lines_per_caption: int
    def __init__(self, segments: _Optional[_Iterable[_Union[TranscriptSegment, _Mapping]]] = ..., max_chars_per_line: _Optional[int] = ..., max_lines_per_caption: _Optional[int] = ...) -> None: ...

class FormatCaptionsResponse(_message.Message):
    __slots__ = ("srt_content",)
    SRT_CONTENT_FIELD_NUMBER: _ClassVar[int]
    srt_content: str
    def __init__(self, srt_content: _Optional[str] = ...) -> None: ...
