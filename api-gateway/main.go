package main

import (
	"log"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"videothingy/api-gateway/config"
	"videothingy/api-gateway/handlers"
)

func main() {
	// Initialize Supabase client
	err := config.InitSupabase()
	if err != nil {
		log.Fatalf("Failed to initialize Supabase: %v", err)
	}

	app := fiber.New()

	// Middleware
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*", // Allow all origins for development
		AllowHeaders: "Origin, Content-Type, Accept",
	}))
	app.Use(logger.New())

	// Health check route
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.Status(fiber.StatusOK).JSON(fiber.Map{
			"status":  "ok",
			"message": "API Gateway is healthy",
		})
	})

	// API v1 routes
	apiV1 := app.Group("/api/v1")

	// Video upload route
	apiV1.Post("/videos/upload", handlers.UploadVideo)

	// Project routes
	apiV1.Post("/projects", handlers.CreateProject)
	apiV1.Get("/projects", handlers.GetProjects)
	apiV1.Get("/projects/:id", handlers.GetProject)
	apiV1.Patch("/projects/:id", handlers.UpdateProject) // Added for updating projects
	apiV1.Delete("/projects/:id", handlers.DeleteProject)

	// Clip routes within a project
	projectClips := apiV1.Group("/projects/:projectId/clips")

	projectClips.Get("", handlers.ListClips)
	projectClips.Post("", handlers.CreateClip)
	projectClips.Get("/:clipId", handlers.GetClip)
	projectClips.Patch("/:clipId", handlers.UpdateClip) // Changed from Put to Patch
	projectClips.Delete("/:clipId", handlers.DeleteClip)

	log.Println("Starting API Gateway on port 8080...")
	log.Fatal(app.Listen(":8080"))
}
