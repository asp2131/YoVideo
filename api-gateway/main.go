package main

import (
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/recover"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/handlers"
	"videothingy/api-gateway/internal/aiclient"
	"videothingy/api-gateway/middleware"
)

func main() {
	// Initialize logger first (uses global config.Log)
	config.InitLogger()

	// Initialize Supabase client (uses global config.SupabaseClient and hardcoded values)
	if err := config.InitSupabase(); err != nil {
		log.Fatalf("Failed to initialize Supabase client: %v", err) // Use standard log, config.Log might not be fully ready
	}

	// Initialize AI Client
	// The AI Service address might come from env or config later
	aiClient, err := aiclient.NewAIClient("localhost:50051") // Corrected: No logger argument
	if err != nil {
		config.Log.Fatalf("Failed to initialize AI client: %v", err)
	}
	defer aiClient.Close() // Ensure gRPC connection is closed when main exits

	// Create a new Fiber app instance with custom error handling
	app := fiber.New(fiber.Config{
		// ErrorHandler: utils.CustomErrorHandler, // Removed custom error handler for now
		BodyLimit: 1 * 1024 * 1024 * 1024, // 1 GB limit for large video uploads
	})

	// Middleware
	app.Use(recover.New()) // Recovers from panics anywhere in the stack chain
	app.Use(cors.New(cors.Config{
		AllowOrigins:     "http://localhost:3000", // Specify frontend origin
		AllowMethods:     "GET,POST,HEAD,PUT,DELETE,PATCH,OPTIONS",
		AllowHeaders:     "Origin, Content-Type, Accept, Authorization",
		AllowCredentials: true,
	}))
	app.Use(middleware.RequestLogger()) // Corrected: No arguments needed

	// Create an instance of ApplicationHandler with dependencies
	appHandler := handlers.NewApplicationHandler(aiClient, config.Log, config.SupabaseClient)

	// Setup routes
	api := app.Group("/api")
	v1 := api.Group("/v1")

	// --- Project Routes ---
	projectsGroup := v1.Group("/projects")
	projectsGroup.Post("/", handlers.CreateProject) 
	projectsGroup.Get("/", handlers.GetProjects)
	projectsGroup.Get("/:id", handlers.GetProject) 
	projectsGroup.Delete("/:id", handlers.DeleteProject)

	// --- Video Routes ---
	videosGroup := projectsGroup.Group("/:projectId/videos") // Corrected: Use Group instead of Path
	videosGroup.Get("/", appHandler.ListVideos) // List all videos for a project
	videosGroup.Post("/initiate-upload", appHandler.InitiateVideoUpload) // Uncommented: Initiate video upload
	videosGroup.Post("/:videoId/upload", appHandler.UploadFileHandler) // Direct upload endpoint to avoid CORS issues
	videosGroup.Post("/:videoId/trigger-transcription", appHandler.TriggerTranscription)
	videosGroup.Get("/:videoId/transcription", appHandler.GetVideoTranscription) // Get video transcription
	videosGroup.Get("/:videoId/processed", appHandler.GetProcessedVideo) // Get processed video with captions
	videosGroup.Post("/:videoId/process-captions", appHandler.ProcessCaptions) // Process video with caption overlay

	// Start the server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	config.Log.Infof("Server starting on port %s", port)
	if err := app.Listen(":" + port); err != nil {
		config.Log.Fatalf("Failed to start server: %v", err)
	}
}
