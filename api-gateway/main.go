package main

// @title OpusClip API Gateway
// @version 1.0
// @description This is the API gateway for the OpusClip video processing service.
// @termsOfService http://example.com/terms/
// @contact.name API Support
// @contact.url http://example.com/support
// @contact.email support@example.com
// @license.name Apache 2.0
// @license.url http://www.apache.org/licenses/LICENSE-2.0.html
// @host localhost:8080
// @BasePath /api/v1
// @schemes http https

import (
	"log"

	"strings"
	"videothingy/api-gateway/config"
	_ "videothingy/api-gateway/docs" // Import generated docs (note the underscore)
	"videothingy/api-gateway/handlers"
	"videothingy/api-gateway/middleware"
	"videothingy/api-gateway/utils"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	fiberSwagger "github.com/swaggo/fiber-swagger" // fiber-swagger middleware

	aiclient "videothingy/api-gateway/internal/aiclient"
)

func main() {
	// Initialize Supabase client
	err := config.InitSupabase()
	if err != nil {
		log.Fatalf("Failed to initialize Supabase: %v", err)
	}

	// Initialize Logger
	config.InitLogger()
	config.Log.Info("Logger initialized") // Example log

	// Initialize AI Client
	aiServiceAddr := config.AppConfig.AIServiceAddress // "localhost:50051" // Make this configurable
	aiClient, err := aiclient.NewAIClient(aiServiceAddr)
	if err != nil {
		config.Log.Fatalf("Failed to create AI client: %v", err)
	}
	defer aiClient.Close()

	// Initialize Validator
	validatorInstance, err := validation.NewValidator(&config.AppConfig.ValidationService, config.Log)
	if err != nil {
		config.Log.Fatalf("Failed to initialize validator: %v", err)
	}

	// Create an instance of ApplicationHandler with all dependencies
	appHandler := handlers.NewApplicationHandler(aiClient, config.Log, config.SupabaseClient, validatorInstance)

	// Create Fiber app
	app := fiber.New()

	// Custom ErrorHandler
	app.Use(func(c *fiber.Ctx) error {
		err := c.Next()
		if err != nil {
			// Use our standard error response utility
			// This part needs to be careful to not cause an error loop if utils.RespondWithError itself errors.
			// However, utils.RespondWithError just calls c.Status().JSON() which is standard.
			if ferr, ok := err.(*fiber.Error); ok {
				return utils.RespondWithError(c, ferr.Code, ferr.Message)
			}

			if validationErrs, ok := err.(validator.ValidationErrors); ok {
				formattedErrors := utils.FormatValidationErrors(validationErrs)
				return utils.RespondWithError(c, fiber.StatusBadRequest, strings.Join(formattedErrors, "; "))
			}

			// Default to 500 Internal Server Error
			// In a real production app, you might want to hide err.Error() from the client
			// and log it instead, returning a generic message.
			log.Printf("Unhandled error: %v", err) // Log the actual error
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal server error occurred.")
		}
		return nil
	})

	// Middleware
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*", // Allow all origins for development
		AllowHeaders: "Origin, Content-Type, Accept",
	}))
	app.Use(middleware.RequestLogger()) // Use our custom Logrus request logger

	// Health check route
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.Status(fiber.StatusOK).JSON(fiber.Map{
			"status":  "ok",
			"message": "API Gateway is healthy",
		})
	})

	// API v1 routes
	apiV1 := app.Group("/api/v1")

	// Video upload route - updated for presigned URL flow
	apiV1.Post("/projects/:projectId/videos/initiate-upload", handlers.InitiateVideoUpload)

	// Project routes
	apiV1.Post("/projects", handlers.CreateProject)
	apiV1.Get("/projects", handlers.GetProjects)
	apiV1.Get("/projects/:id", handlers.GetProject)
	apiV1.Patch("/projects/:id", handlers.UpdateProject) // Added for updating projects
	apiV1.Delete("/projects/:id", handlers.DeleteProject)

	// Job Status Route
	apiV1.Get("/jobs/:jobId", handlers.GetJobStatus) // GET /api/v1/jobs/:jobId

	// Group for project-specific routes
	projectsGroup := apiV1.Group("/projects/:projectId")

	projectsGroup.Get("/clips", handlers.ListClips)
	projectsGroup.Post("/clips", handlers.CreateClip)
	projectsGroup.Get("/clips/:clipId", handlers.GetClip)
	projectsGroup.Patch("/clips/:clipId", handlers.UpdateClip) // Changed from Put to Patch
	projectsGroup.Delete("/clips/:clipId", handlers.DeleteClip)

	// Clip download route
	projectsGroup.Get("/clips/:clipId/download", handlers.GetClipDownloadURL) // GET /api/v1/projects/:projectId/clips/:clipId/download

	// Source Video Routes (nested under projects for now, as they are project-specific)
	// It's better to keep source video routes separate if they are not strictly dependent on a projectId for their core logic beyond initial upload.
	// However, if a source video is always tied to a project contextually, this nesting is fine.
	// For now, assuming source_videos always belong to a project:
	projectsGroup.Post("/source-videos", appHandler.InitiateVideoUpload) // projectsGroup.Get("/source-videos", handlers.ListSourceVideos)                     // GET /api/v1/projects/:projectId/source-videos
	// projectsGroup.Get("/source-videos/:sourceVideoId", handlers.GetSourceVideo)         // GET /api/v1/projects/:projectId/source-videos/:sourceVideoId
	// projectsGroup.Patch("/source-videos/:sourceVideoId", handlers.UpdateSourceVideo)     // PATCH /api/v1/projects/:projectId/source-videos/:sourceVideoId
	// projectsGroup.Delete("/source-videos/:sourceVideoId", handlers.DeleteSourceVideo)   // DELETE /api/v1/projects/:projectId/source-videos/:sourceVideoId

	// Caption routes within a clip
	clipCaptions := projectsGroup.Group("/clips/:clipId/captions")

	clipCaptions.Post("", handlers.CreateCaption)
	clipCaptions.Get("", handlers.ListCaptions)
	clipCaptions.Get("/:captionId", handlers.GetCaption)       // Placeholder
	clipCaptions.Patch("/:captionId", handlers.UpdateCaption)  // Placeholder, using PATCH for consistency
	clipCaptions.Delete("/:captionId", handlers.DeleteCaption) // Placeholder

	// Trigger Transcription Route
	projectsGroup.Post("/source-videos/:videoId/transcribe", appHandler.TriggerTranscription)

	// Swagger UI route
	// Note: The BasePath in the general annotations is /api/v1,
	// so swagger will try to hit endpoints like /api/v1/projects, not /swagger/api/v1/projects
	app.Get("/swagger/*", fiberSwagger.WrapHandler)

	config.Log.Info("Starting API Gateway on port 8080...")
	log.Fatal(app.Listen(":8080"))
}
