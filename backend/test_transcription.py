import grpc
import ai_service_pb2
import ai_service_pb2_grpc
import json

def main():
    # Connect to the gRPC server
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = ai_service_pb2_grpc.AIServiceStub(channel)
        
        # Create a request to transcribe the video
        request = ai_service_pb2.TranscribeAudioRequest(
            video_storage_path="test_upload/test.mp4",
            original_filename="test.mp4"
        )
        
        print("Sending transcription request...")
        
        # Call the TranscribeAudio method
        try:
            response = stub.TranscribeAudio(request)
            
            # Print the transcription results
            print(f"Transcription completed for: {response.filename}")
            print(f"Number of segments: {len(response.segments)}")
            
            # Convert the response to a dictionary for JSON serialization
            transcription = {
                "text": " ".join([segment.text for segment in response.segments]),
                "segments": [
                    {
                        "text": segment.text,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time
                    }
                    for segment in response.segments
                ]
            }
            
            # Save the transcription to a file
            with open("transcription_result.json", "w") as f:
                json.dump(transcription, f, indent=2)
                
            print(f"Transcription saved to transcription_result.json")
            
            # Now test highlight detection
            highlight_request = ai_service_pb2.DetectHighlightsRequest(
                segments=[
                    ai_service_pb2.TranscriptSegment(
                        text=segment.text,
                        start_time=segment.start_time,
                        end_time=segment.end_time
                    )
                    for segment in response.segments
                ]
            )
            
            print("Sending highlight detection request...")
            highlight_response = stub.DetectHighlights(highlight_request)
            
            print(f"Number of highlights detected: {len(highlight_response.highlights)}")
            
            # Convert highlights to a dictionary
            highlights = [
                {
                    "text": highlight.text,
                    "start_time": highlight.start_time,
                    "end_time": highlight.end_time,
                    "score": highlight.score
                }
                for highlight in highlight_response.highlights
            ]
            
            # Save highlights to a file
            with open("highlights_result.json", "w") as f:
                json.dump(highlights, f, indent=2)
                
            print(f"Highlights saved to highlights_result.json")
            
        except grpc.RpcError as e:
            print(f"RPC error: {e.code()}: {e.details()}")

if __name__ == "__main__":
    main()
