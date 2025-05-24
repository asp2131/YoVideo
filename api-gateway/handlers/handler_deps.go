package handlers

import (
	"context"

	supa "github.com/supabase-community/supabase-go"
	"github.com/sirupsen/logrus"

	// Import the generated gRPC client code for response/request types if needed by the interface
	aiservice "videothingy/api-gateway/internal/goclient/aiservice"
)

// AIClientInterface defines the operations handlers expect from an AI client.
// This allows for decoupling and easier testing.
// The concrete implementation will be provided by the aiclient package.
type AIClientInterface interface {
	TranscribeAudio(ctx context.Context, videoStoragePath string, originalFilename string) (*aiservice.TranscribeAudioResponse, error)
	DetectHighlights(ctx context.Context, segments []*aiservice.TranscriptSegment) (*aiservice.DetectHighlightsResponse, error)
	FormatCaptions(ctx context.Context, segments []*aiservice.TranscriptSegment, maxChars int32, maxLines int32) (*aiservice.FormatCaptionsResponse, error)
	Close() error
}

// ApplicationHandler holds shared dependencies for handlers.
type ApplicationHandler struct {
	AIClient   AIClientInterface // Use the interface
	Logger     *logrus.Logger
	DB         *supa.Client
	// Supabase *supabase.Client // Example: if you pass Supabase client directly
}

// NewApplicationHandler creates a new ApplicationHandler with the given dependencies.
func NewApplicationHandler(aiClient AIClientInterface, logger *logrus.Logger, dbClient *supa.Client) *ApplicationHandler {
	return &ApplicationHandler{
		AIClient:   aiClient,
		Logger:     logger,
		DB:         dbClient,
	}
}
