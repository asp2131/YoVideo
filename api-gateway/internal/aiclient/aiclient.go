package aiclient

import (
	"context"
	"fmt"
	"log"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	// Import the generated gRPC client code
	aiservice "videothingy/api-gateway/internal/goclient/aiservice"
)

// AIClient wraps the gRPC client for the AI service.
// We can add methods to this struct later to call specific RPCs.
type AIClient struct {
	grpcClient aiservice.AIServiceClient
	conn       *grpc.ClientConn // Store the connection to close it later
}

// NewAIClient creates and returns a new AIClient.
func NewAIClient(serverAddr string) (*AIClient, error) {
	log.Printf("Attempting to connect to AI gRPC server at %s", serverAddr)

	// Set up a connection to the server.
	// For this example, we're using an insecure connection.
	// In a production environment, you'd use TLS credentials.
	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Printf("Failed to connect to AI gRPC server: %v", err)
		return nil, err
	}
	// Note: The connection 'conn' should ideally be closed when the application shuts down.
	// We'll need to manage its lifecycle, perhaps when integrating into the main API gateway app.

	client := aiservice.NewAIServiceClient(conn)
	log.Printf("Successfully connected to AI gRPC server at %s", serverAddr)

	return &AIClient{grpcClient: client, conn: conn}, nil
}

// Close closes the gRPC connection to the AI service.
func (c *AIClient) Close() error {
	if c.conn != nil {
		log.Printf("Closing connection to AI gRPC server")
		return c.conn.Close()
	}
	return nil
}

// GetGRPCClient returns the raw gRPC client.
// This can be used if direct access to the gRPC client methods is needed,
// though it's generally better to wrap specific RPC calls in methods on AIClient.
func (c *AIClient) GetGRPCClient() aiservice.AIServiceClient {
	return c.grpcClient
}

// TranscribeAudio sends an audio transcription request to the AI service.
// It sends the storage path of the video file to the AI service.
func (c *AIClient) TranscribeAudio(ctx context.Context, videoStoragePath string, originalFilename string) (*aiservice.TranscribeAudioResponse, error) {
	log.Printf("AIClient: Sending transcription request for video path %s (original file: %s)", videoStoragePath, originalFilename)
	
	// Create the request with the video storage path
	request := &aiservice.TranscribeAudioRequest{
		VideoStoragePath: videoStoragePath,
		OriginalFilename: originalFilename,
	}
	
	// Call the gRPC service
	response, err := c.grpcClient.TranscribeAudio(ctx, request)
	if err != nil {
		log.Printf("AIClient: TranscribeAudio RPC failed for %s: %v", originalFilename, err)
		return nil, fmt.Errorf("AI service error: %v", err)
	}
	
	log.Printf("AIClient: Successfully transcribed %s", originalFilename)
	return response, nil
}

// DetectHighlights sends a request to the AI service to detect highlights in the provided transcript segments.
// It takes a slice of TranscriptSegment and returns a DetectHighlightsResponse with the detected highlights.
func (c *AIClient) DetectHighlights(ctx context.Context, segments []*aiservice.TranscriptSegment) (*aiservice.DetectHighlightsResponse, error) {
	log.Printf("AIClient: Sending highlight detection request for %d segments", len(segments))
	
	// Create the request with the transcript segments
	request := &aiservice.DetectHighlightsRequest{
		Segments: segments,
	}
	
	// Call the gRPC service
	response, err := c.grpcClient.DetectHighlights(ctx, request)
	if err != nil {
		log.Printf("AIClient: DetectHighlights RPC failed: %v", err)
		return nil, fmt.Errorf("AI service error during highlight detection: %v", err)
	}
	
	log.Printf("AIClient: Successfully detected %d highlights", len(response.GetHighlights()))
	return response, nil
}

// FormatCaptions sends a request to the AI service to format captions for the provided transcript segments.
// It takes a slice of TranscriptSegment and formatting options, then returns a FormatCaptionsResponse with the formatted captions.
func (c *AIClient) FormatCaptions(ctx context.Context, segments []*aiservice.TranscriptSegment, maxChars int32, maxLines int32) (*aiservice.FormatCaptionsResponse, error) {
    log.Printf("AIClient: Sending caption formatting request for %d segments", len(segments))
    
    // Create the request with the transcript segments and formatting options
    request := &aiservice.FormatCaptionsRequest{
        Segments:           segments,
        MaxCharsPerLine:    maxChars,
        MaxLinesPerCaption: maxLines,
    }
    
    // Call the gRPC service
    response, err := c.grpcClient.FormatCaptions(ctx, request)
    if err != nil {
        log.Printf("AIClient: FormatCaptions RPC failed: %v", err)
        return nil, fmt.Errorf("AI service error during caption formatting: %v", err)
    }
    
    log.Printf("AIClient: Successfully formatted captions (response length: %d chars)", len(response.GetSrtContent()))
    return response, nil
}
