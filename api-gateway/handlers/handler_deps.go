package handlers

import (
	aiclient "videothingy/api-gateway/internal/aiclient"
	"github.com/nedpals/postgrest-go/v2"
	"github.com/sirupsen/logrus"
)

// ApplicationHandler holds shared dependencies for HTTP handlers.
// This makes it easy to pass dependencies like database connections, gRPC clients,
// loggers, etc., to your handler functions in a structured and testable way.
type ApplicationHandler struct {
	AIClient *aiclient.AIClient
	Logger   *logrus.Logger // Use the actual type from the logrus package
	DB       *postgrest.Client
	// Supabase *supabase.Client // Example: if you pass Supabase client directly
}

// NewApplicationHandler creates a new ApplicationHandler with the given dependencies.
func NewApplicationHandler(aiClient *aiclient.AIClient, logger *logrus.Logger, dbClient *postgrest.Client) *ApplicationHandler {
	return &ApplicationHandler{
		AIClient: aiClient,
		Logger:   logger,
		DB:       dbClient,
	}
}
