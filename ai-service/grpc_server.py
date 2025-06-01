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
from main import whisper_model, TranscriptSegment, CaptionFormatRequest, CaptionFormatResponse, format_srt_time, break_text_into_lines

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AIServiceServicer(ai_service_pb2_grpc.AIServiceServicer):
    def TranscribeAudio(self, request: ai_service_pb2.TranscribeAudioRequest, context):
        logger.info(f"gRPC TranscribeAudio called for {request.original_filename}")
        if whisper_model is None:
            error_msg = "Whisper model is not available."
            logger.error(error_msg)
            context.abort(grpc.StatusCode.INTERNAL, error_msg)
            return ai_service_pb2.TranscribeAudioResponse()

        import requests
        from urllib.parse import urljoin
        import subprocess
        
        tmp_video_path = None
        tmp_audio_path = None
        
        try:
            # Construct the full URL to the file in Supabase storage
            supabase_url = "https://whwbduaefolbnfdrcfuo.supabase.co/storage/v1/object/public/source-videos/"
            video_url = urljoin(supabase_url, request.video_storage_path)
            
            logger.info(f"Downloading video from: {video_url}")
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            # Create a temporary file to store the video with a proper extension
            suffix = os.path.splitext(request.original_filename)[1] if request.original_filename else ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_video_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_video_file.write(chunk)
                tmp_video_path = tmp_video_file.name
                
            logger.info(f"Temporary video file saved at: {tmp_video_path}")
            
            # Verify the file was downloaded correctly
            if not os.path.exists(tmp_video_path) or os.path.getsize(tmp_video_path) == 0:
                error_msg = f"Failed to download video file from {video_url} - file is empty or doesn't exist"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            file_size = os.path.getsize(tmp_video_path)
            logger.info(f"Successfully downloaded {file_size} bytes")
            
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_audio_file:
                tmp_audio_path = tmp_audio_file.name
                
            # Extract audio using ffmpeg
            logger.info(f"Extracting audio from {tmp_video_path} to {tmp_audio_path}")
            try:
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output file if it exists
                    '-i', tmp_video_path,  # Input file
                    '-vn',  # Disable video recording
                    '-acodec', 'pcm_s16le',  # Audio codec
                    '-ar', '16000',  # Audio sample rate
                    '-ac', '1',  # Mono audio
                    '-f', 'wav',  # Output format
                    tmp_audio_path
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    error_msg = f"FFmpeg error: {result.stderr}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
                logger.info(f"Successfully extracted audio to {tmp_audio_path}")
                
            except Exception as e:
                error_msg = f"Error extracting audio: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Verify the audio file was created and has content
            if not os.path.exists(tmp_audio_path) or os.path.getsize(tmp_audio_path) == 0:
                error_msg = "Failed to extract audio - output file is empty or doesn't exist"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Transcribe the audio file
            logger.info(f"Starting transcription for {request.original_filename}")
            try:
                result = whisper_model.transcribe(tmp_audio_path, fp16=False)  # fp16=False for CPU
                logger.info("Transcription completed successfully")
                
                response_segments = []
                for seg in result.get("segments", []):
                    segment_text = seg.get("text", "").strip()
                    if segment_text:  # Only include non-empty segments
                        response_segments.append(
                            ai_service_pb2.TranscriptSegment(
                                text=segment_text,
                                start_time=seg.get("start", 0.0),
                                end_time=seg.get("end", 0.0)
                            )
                        )
                
                logger.info(f"Processed {len(response_segments)} non-empty segments")
                
                if not response_segments:
                    logger.warning("No transcription segments were generated. This might indicate an issue with the audio.")
                
                return ai_service_pb2.TranscribeAudioResponse(
                    filename=request.original_filename,
                    segments=response_segments
                )
                
            except Exception as e:
                error_msg = f"Error during transcription: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            error_msg = f"Error in TranscribeAudio: {str(e)}"
            logger.error(error_msg)
            context.abort(grpc.StatusCode.INTERNAL, error_msg)
            return ai_service_pb2.TranscribeAudioResponse()
            
        finally:
            # Clean up temporary files
            for file_path in [tmp_video_path, tmp_audio_path]:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {file_path}: {str(e)}")

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
