package aiclient

import (
	"log"
	"context"

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
// It now takes a videoStoragePath instead of raw audioData.
func (c *AIClient) TranscribeAudio(ctx context.Context, videoStoragePath string, originalFilename string) (*aiservice.TranscribeAudioResponse, error) {
	log.Printf("AIClient: Sending TranscribeAudio request for video path %s (original file: %s)", videoStoragePath, originalFilename)
	request := &aiservice.TranscribeAudioRequest{
		// AudioData:        audioData, // Field removed from .proto
		VideoStoragePath: videoStoragePath,
		OriginalFilename: originalFilename,
	}
	
	// Add a timeout to the context for the gRPC call
	// ctx, cancel := context.WithTimeout(ctx, time.Second*30) // Example 30-second timeout
	// defer cancel()

	response, err := c.grpcClient.TranscribeAudio(ctx, request)
	if err != nil {
		log.Printf("AIClient: TranscribeAudio RPC failed for %s: %v", originalFilename, err)
		return nil, err
	}
	log.Printf("AIClient: Received TranscribeAudio response for %s", originalFilename)
	return response, nil
}

/*
// Example for DetectHighlights
func (c *AIClient) DetectHighlights(ctx context.Context, segments []*aiservice.TranscriptSegment) (*aiservice.DetectHighlightsResponse, error) {
    request := &aiservice.DetectHighlightsRequest{Segments: segments}
    return c.grpcClient.DetectHighlights(ctx, request)
}

// Example for FormatCaptions
func (c *AIClient) FormatCaptions(ctx context.Context, segments []*aiservice.TranscriptSegment, maxChars int32, maxLines int32) (*aiservice.FormatCaptionsResponse, error) {
    request := &aiservice.FormatCaptionsRequest{
        Segments:           segments,
        MaxCharsPerLine:    maxChars,
        MaxLinesPerCaption: maxLines,
    }
    return c.grpcClient.FormatCaptions(ctx, request)
}
*/
