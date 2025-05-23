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
	})

	// Middleware
	app.Use(recover.New()) // Recovers from panics anywhere in the stack chain
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*", // Allow all origins for now, restrict in production
		AllowMethods: "GET,POST,HEAD,PUT,DELETE,PATCH,OPTIONS",
		AllowHeaders: "Origin, Content-Type, Accept, Authorization",
	}))
	app.Use(middleware.RequestLogger()) // Corrected: No arguments needed

	// Create an instance of ApplicationHandler with dependencies
	appHandler := handlers.NewApplicationHandler(aiClient, config.Log, config.SupabaseClient)

	// Setup routes
	api := app.Group("/api")
	v1 := api.Group("/v1")

	// --- Project Routes (Example, assuming these handlers exist on ApplicationHandler) ---
	projectsGroup := v1.Group("/projects")
	// projectsGroup.Post("/", appHandler.CreateProject) // Temporarily commented out to avoid undefined error
	// projectsGroup.Get("/", appHandler.GetProjects)       // Commented out
	// projectsGroup.Get("/:projectId", appHandler.GetProject) // Commented out
	// projectsGroup.Patch("/:projectId", appHandler.UpdateProject) // Commented out
	// projectsGroup.Delete("/:projectId", appHandler.DeleteProject) // Commented out

	// --- Video Routes ---
	videosGroup := projectsGroup.Group("/:projectId/videos") // Corrected: Use Group instead of Path
	videosGroup.Post("/initiate-upload", appHandler.InitiateVideoUpload) // Uncommented: Initiate video upload
	videosGroup.Post("/:videoId/trigger-transcription", appHandler.TriggerTranscription)
	videosGroup.Get("/:videoId/transcription", appHandler.GetVideoTranscription) // Get video transcription

	// --- Clip Routes (Example) ---
	// clipsGroup := projectsGroup.Path("/:projectId/clips")
	// clipsGroup.Post("/", appHandler.CreateClip) // Commented out
	// clipsGroup.Get("/", appHandler.ListClips)       // Commented out
	// clipsGroup.Get("/:clipId", appHandler.GetClip) // Commented out
	// clipsGroup.Patch("/:clipId", appHandler.UpdateClip) // Commented out
	// clipsGroup.Delete("/:clipId", appHandler.DeleteClip) // Commented out

	// --- Caption Routes (Example) ---
	// captionsGroup := clipsGroup.Path("/:clipId/captions")
	// captionsGroup.Post("/", appHandler.CreateCaption) // Commented out
	// captionsGroup.Get("/", appHandler.ListCaptions)       // Commented out
	// captionsGroup.Get("/:captionId", appHandler.GetCaption) // Commented out
	// captionsGroup.Patch("/:captionId", appHandler.UpdateCaption) // Commented out
	// captionsGroup.Delete("/:captionId", appHandler.DeleteCaption) // Commented out

	// --- Job Status Route (Example) ---
	// v1.Get("/jobs/:jobId/status", appHandler.GetJobStatus) // Commented out

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
