import grpc
from concurrent import futures
import time
import logging
import os
import tempfile
import shutil

# Generated gRPC files
import ai_service_pb2
import ai_service_pb2_grpc

# Import components from main.py (FastAPI app)
# We need the whisper_model and the Pydantic models for data conversion if necessary,
# and potentially the core logic of highlight detection and caption formatting.
# This might require some refactoring in main.py if imports cause issues (e.g., auto-starting FastAPI).
from main import whisper_model, TranscriptSegment, HighlightDetectionRequest, Highlight, HighlightDetectionResponse, CaptionFormatRequest, CaptionFormatResponse, format_srt_time, break_text_into_lines, INTERESTING_KEYWORDS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AIServiceServicer(ai_service_pb2_grpc.AIServiceServicer):
    def TranscribeAudio(self, request: ai_service_pb2.TranscribeAudioRequest, context):
        logger.info(f"gRPC TranscribeAudio called for {request.original_filename}")
        if whisper_model is None:
            context.abort(grpc.StatusCode.INTERNAL, "Whisper model is not available.")
            return ai_service_pb2.TranscribeAudioResponse()

        tmp_audio_file_path = None
        try:
            # Create a temporary file to store the uploaded audio bytes
            # Whisper needs a file path to process.
            # Use a generic suffix if original_filename doesn't provide one, or handle it.
            suffix = os.path.splitext(request.original_filename)[1] if request.original_filename else ".tmp"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_audio_file:
                tmp_audio_file.write(request.audio_data)
                tmp_audio_file_path = tmp_audio_file.name
            logger.info(f"Temporary audio file for gRPC saved at: {tmp_audio_file_path}")

            # Transcribe the audio file
            logger.info(f"Starting transcription for {tmp_audio_file_path} via gRPC...")
            result = whisper_model.transcribe(tmp_audio_file_path, fp16=False) # fp16=False for CPU
            logger.info(f"Transcription successful via gRPC. Processing segments...")

            response_segments = []
            for seg in result.get("segments", []):
                response_segments.append(
                    ai_service_pb2.TranscriptSegment(
                        text=seg.get("text", ""),
                        start_time=seg.get("start", 0.0),
                        end_time=seg.get("end", 0.0)
                    )
                )
            logger.info(f"Processed {len(response_segments)} segments for gRPC response.")
            
            return ai_service_pb2.TranscribeAudioResponse(
                filename=request.original_filename,
                segments=response_segments
            )

        except Exception as e:
            logger.error(f"Error during gRPC TranscribeAudio: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Error during transcription: {str(e)}")
            return ai_service_pb2.TranscribeAudioResponse() # Should not be reached if abort works
        finally:
            if tmp_audio_file_path and os.path.exists(tmp_audio_file_path):
                os.remove(tmp_audio_file_path)
                logger.info(f"Temporary audio file {tmp_audio_file_path} deleted.")

    def DetectHighlights(self, request: ai_service_pb2.DetectHighlightsRequest, context):
        logger.info(f"gRPC DetectHighlights called with {len(request.segments)} segments.")
        detected_highlights_proto = []
        min_score_to_include = 1 # As defined in main.py

        # Convert protobuf segments to Pydantic TranscriptSegment for logic reuse (if any)
        # Or directly iterate and apply logic
        pydantic_segments = [
            TranscriptSegment(text=s.text, start_time=s.start_time, end_time=s.end_time)
            for s in request.segments
        ]

        for p_segment in pydantic_segments:
            score = 0
            segment_text_lower = p_segment.text.lower()
            for keyword in INTERESTING_KEYWORDS:
                if keyword.lower() in segment_text_lower:
                    score += 1
            
            if score >= min_score_to_include:
                detected_highlights_proto.append(
                    ai_service_pb2.Highlight(
                        text=p_segment.text,
                        start_time=p_segment.start_time,
                        end_time=p_segment.end_time,
                        score=float(score)
                    )
                )
        
        logger.info(f"Detected {len(detected_highlights_proto)} highlights via gRPC.")
        return ai_service_pb2.DetectHighlightsResponse(highlights=detected_highlights_proto)

    def FormatCaptions(self, request: ai_service_pb2.FormatCaptionsRequest, context):
        logger.info(f"gRPC FormatCaptions called with {len(request.segments)} segments.")
        srt_blocks = []

        # Convert protobuf segments to Pydantic for easier handling if needed, or use directly
        # For this logic, direct use is fine, but Pydantic conversion shown for consistency pattern
        pydantic_segments = [
            TranscriptSegment(text=s.text, start_time=s.start_time, end_time=s.end_time)
            for s in request.segments
        ]

        max_chars = request.max_chars_per_line if request.max_chars_per_line > 0 else 40
        max_lines = request.max_lines_per_caption if request.max_lines_per_caption > 0 else 2

        for i, p_segment in enumerate(pydantic_segments):
            start_srt_time = format_srt_time(p_segment.start_time)
            end_srt_time = format_srt_time(p_segment.end_time)
            
            caption_lines = break_text_into_lines(
                p_segment.text,
                max_chars, # Use from request or default
                max_lines  # Use from request or default
            )
            
            if not caption_lines:
                continue
                
            srt_block = f"{i+1}\n"
            srt_block += f"{start_srt_time} --> {end_srt_time}\n"
            srt_block += "\n".join(caption_lines)
            srt_block += "\n\n"
            srt_blocks.append(srt_block)
            
        final_srt_content = "".join(srt_blocks).strip()
        logger.info(f"Formatted SRT content generated via gRPC, length: {len(final_srt_content)} chars.")
        return ai_service_pb2.FormatCaptionsResponse(srt_content=final_srt_content)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ai_service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)
    port = "[::]:50051" # Standard gRPC port
    server.add_insecure_port(port)
    logger.info(f"Starting gRPC server on {port}")
    server.start()
    logger.info("gRPC server started.")
    try:
        while True:
            time.sleep(86400)  # One day in seconds
    except KeyboardInterrupt:
        logger.info("Stopping gRPC server...")
        server.stop(0)
        logger.info("gRPC server stopped.")

if __name__ == '__main__':
    serve()
