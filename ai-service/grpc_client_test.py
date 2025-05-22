import grpc
import logging

# Generated gRPC files
import ai_service_pb2
import ai_service_pb2_grpc

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def run_transcribe_test(audio_file_path="test.mp3"):
    channel_address = 'localhost:50051'
    logger.info(f"Attempting to connect to gRPC server at {channel_address}")
    try:
        with grpc.insecure_channel(channel_address) as channel:
            stub = ai_service_pb2_grpc.AIServiceStub(channel)
            logger.info("gRPC channel connected. Reading audio file...")
            
            try:
                with open(audio_file_path, 'rb') as f:
                    audio_data = f.read()
                logger.info(f"Audio file '{audio_file_path}' read successfully ({len(audio_data)} bytes).")
            except FileNotFoundError:
                logger.error(f"Audio file '{audio_file_path}' not found. Please ensure it's in the same directory or provide the correct path.")
                return
            except Exception as e:
                logger.error(f"Error reading audio file '{audio_file_path}': {e}")
                return

            request = ai_service_pb2.TranscribeAudioRequest(
                audio_data=audio_data,
                original_filename=audio_file_path
            )
            
            logger.info(f"Sending TranscribeAudio request for {audio_file_path}...")
            response = stub.TranscribeAudio(request)
            
            logger.info(f"Received TranscribeAudio response for filename: {response.filename}")
            logger.info(f"Number of segments: {len(response.segments)}")
            for i, segment in enumerate(response.segments):
                logger.info(f"  Segment {i+1}: [{segment.start_time:.2f}s - {segment.end_time:.2f}s] {segment.text}")
                
    except grpc.RpcError as e:
        logger.error(f"gRPC call failed: {e.status()} - {e.details()}")
        if e.status() == grpc.StatusCode.UNAVAILABLE:
            logger.error("Server unavailable. Is the gRPC server (grpc_server.py) running in another terminal?")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    run_transcribe_test()
    # You can add calls to test other services here later, e.g.:
    # run_detect_highlights_test()
    # run_format_captions_test()
