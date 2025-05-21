package handlers

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// UploadVideoPayload defines the expected JSON structure for uploading a video (metadata only).
type UploadVideoPayload struct {
	Title     string  `json:"title"`
	ProjectID *string `json:"project_id,omitempty"` // Optional project ID
	// In a real scenario, more fields like filename, content_type, size would be here
	// or handled via multipart/form-data for actual file upload.
}

// UploadVideo handles creating a SourceVideo record in the database.
// This version simulates metadata creation post-upload.
func UploadVideo(c *fiber.Ctx) error {
	log.Println("Received request to register a source video")

	payload := new(UploadVideoPayload)
	if err := c.BodyParser(payload); err != nil {
		log.Printf("Error parsing upload video payload: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid request body: %v", err),
		})
	}

	if payload.Title == "" {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'title' is required"})
	}

	var projectUUIDPtr *uuid.UUID
	if payload.ProjectID != nil && *payload.ProjectID != "" {
		parsedUUID, err := uuid.Parse(*payload.ProjectID)
		if err != nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid 'project_id' format"})
		}
		projectUUIDPtr = &parsedUUID
	}

	newSourceVideoID := uuid.New()
	now := time.Now()

	sourceVideo := models.SourceVideo{
		ID:           newSourceVideoID,
		ProjectID:    projectUUIDPtr,
		Title:        payload.Title,
		StoragePath:  fmt.Sprintf("uploads/%s/%s.mp4", newSourceVideoID.String(), payload.Title), // Placeholder path
		Status:       "uploaded",                                                               // Default status
		CreatedAt:    now,
		UpdatedAt:    now,
		// Initialize other required non-nullable fields from models.SourceVideo if any
		// For example, if TranscriptionStatus is NOT NULL and has no default in DB:
		// TranscriptionStatus: new(string), // Or a sensible default like "pending"
	}
	// Defaulting TranscriptionStatus if it's a pointer to string in the model and needs a default
	if sourceVideo.TranscriptionStatus == nil {
		defaultTranscriptionStatus := "not_started"
		sourceVideo.TranscriptionStatus = &defaultTranscriptionStatus
	}

	var results []models.SourceVideo

	bodyBytes, _, err := config.SupabaseClient.From("source_videos").
		Insert(sourceVideo, false, "", "representation", "").
		Execute()

	if err != nil {
		log.Printf("Error creating source video in Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not create source video: %v", err),
		})
	}

	if err := json.Unmarshal(bodyBytes, &results); err != nil {
		log.Printf("Error unmarshalling created source video data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process source video creation response: %v", err),
		})
	}

	if len(results) == 0 {
		log.Println("Source video creation did not return data")
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Source video creation failed to return data",
		})
	}

	log.Printf("Successfully created source video with ID %s", results[0].ID)
	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"status":  "success",
		"message": "Source video registered successfully",
		"data":    results[0],
	})
}
