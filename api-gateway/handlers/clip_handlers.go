package handlers

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"
	"videothingy/api-gateway/utils"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// ListClips retrieves all clips for a specific project.
func ListClips(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	log.Printf("Received request to list clips for project ID: %s", projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		log.Printf("Invalid project ID format: %s", projectIDStr)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Invalid project ID format",
		})
	}

	var clips []models.Clip
	// Query Supabase for clips matching the project_id
	// The .eq method filters for equality, e.g., project_id = projectID
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Select("", "", false).
		Eq("project_id", projectID.String()).
		Execute()

	if err != nil {
		log.Printf("Error fetching clips for project %s from Supabase: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not retrieve clips: %v", err),
		})
	}

	if err := json.Unmarshal(bodyBytes, &clips); err != nil {
		log.Printf("Error unmarshalling clips data for project %s: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process clips data: %v", err),
		})
	}

	if clips == nil {
		// Return an empty list instead of null if no clips are found, which is more idiomatic for lists.
		clips = []models.Clip{}
	}

	log.Printf("Successfully retrieved %d clips for project ID: %s", len(clips), projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Clips retrieved successfully",
		"data":    clips,
	})
}

// ClipSettingsPayload defines the settings for a specific clip to be generated.
type ClipSettingsPayload struct {
	StartTime      float64 `json:"start_time" validate:"required,gte=0"`
	EndTime        float64 `json:"end_time" validate:"required,gtfield=StartTime"`
	CaptionsEnabled *bool   `json:"captions_enabled,omitempty"`
	BRollEnabled    *bool   `json:"b_roll_enabled,omitempty"`
}

// ClipGenerationRequest defines the payload for generating a new clip.
type ClipGenerationRequest struct {
	SourceVideoID string             `json:"source_video_id" validate:"required,uuid"`
	ProjectID     *string            `json:"project_id,omitempty" validate:"omitempty,uuid"` // Optional, but if provided must be UUID
	Title         string             `json:"title" validate:"required"`
	Description   *string            `json:"description,omitempty"`
	AspectRatio   string             `json:"aspect_ratio" validate:"required"` // e.g., "9:16", "1:1"
	TemplateID    *string            `json:"template_id,omitempty" validate:"omitempty,uuid"`
	ClipSettings  ClipSettingsPayload `json:"clip_settings" validate:"required"`
}

// GenerateClipFromSource handles the request to generate a clip from a source video.
func GenerateClipFromSource(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid project ID format")
	}

	var payload ClipGenerationRequest
	if err := c.BodyParser(&payload); err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, fmt.Sprintf("Cannot parse JSON: %v", err))
	}

	validate := validator.New()
	if err := validate.Struct(payload); err != nil {
		errors := utils.FormatValidationErrors(err)
		return utils.RespondWithError(c, fiber.StatusBadRequest, strings.Join(errors, ", "))
	}

	sourceVideoUUID, err := uuid.Parse(payload.SourceVideoID)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid source_video_id format")
	}

	if payload.ProjectID != nil {
		payloadProjectUUID, err := uuid.Parse(*payload.ProjectID)
		if err != nil {
			return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid project_id format in payload")
		}
		if payloadProjectUUID != projectID {
			return utils.RespondWithError(c, fiber.StatusBadRequest, "Project ID in URL and payload do not match")
		}
	}

	// 1. Check that the source video exists, belongs to the project, and is in ready status
	var sourceVideos []models.SourceVideo // Expecting a slice for Supabase client result
	bodyBytes, _, err := config.SupabaseClient.From("source_videos").
		Select("id, status, project_id", "", false).
		Eq("id", sourceVideoUUID.String()).
		Eq("project_id", projectID.String()). // Ensure it belongs to the project
		Execute()
	if err != nil {
		log.Printf("Error fetching source video %s for project %s: %v", sourceVideoUUID, projectID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error checking source video status")
	}
	if err := json.Unmarshal(bodyBytes, &sourceVideos); err != nil {
		log.Printf("Error unmarshalling source video data: %v. Body: %s", err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error processing source video data")
	}
	if len(sourceVideos) == 0 {
		return utils.RespondWithError(c, fiber.StatusNotFound, "Source video not found or does not belong to this project")
	}
	sourceVideo := sourceVideos[0]

	// TODO: Define and use constants for statuses
	if sourceVideo.Status != "uploaded" { // Example status, adjust as needed
		return utils.RespondWithError(c, fiber.StatusConflict, fmt.Sprintf("Source video is not ready for clipping. Current status: %s", sourceVideo.Status))
	}

	// 2. Create a new record in the clips table
	newClipID := uuid.New()
	clip := models.Clip{
		ID:            newClipID,
		SourceVideoID: sourceVideoUUID,
		ProjectID:     &projectID,
		Title:         payload.Title,
		Description:   payload.Description,
		StartTime:     &payload.ClipSettings.StartTime,
		EndTime:       &payload.ClipSettings.EndTime,
		AspectRatio:   &payload.AspectRatio,
		Status:        "processing", 
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}
	if payload.TemplateID != nil {
		templateUUID, err := uuid.Parse(*payload.TemplateID)
		if err != nil {
			return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid template_id format")
		}
		clip.TemplateID = &templateUUID
	}
	clip.CaptionsEnabled = payload.ClipSettings.CaptionsEnabled
	clip.BRollEnabled = payload.ClipSettings.BRollEnabled

	var createdClips []models.Clip
	bodyBytes, _, err = config.SupabaseClient.From("clips").
		Insert(clip, false, "representation", "", "").
		Execute()
	if err != nil {
		log.Printf("Failed to create clip record: %v", err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Failed to create clip record: %v", err))
	}
	if err := json.Unmarshal(bodyBytes, &createdClips); err != nil || len(createdClips) == 0 {
		log.Printf("Failed to unmarshal created clip or empty result: %v. Body: %s", err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Failed to process clip creation response")
	}

	// 3. Create a processing job in the processing_jobs table
	jobID := uuid.New()
	processingJob := models.ProcessingJob{
		ID:         jobID,
		JobType:    "clip_generation",
		EntityID:   newClipID,
		EntityType: "clip",
		Status:     "queued",
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}
	var createdJobs []models.ProcessingJob
	bodyBytes, _, err = config.SupabaseClient.From("processing_jobs").
		Insert(processingJob, false, "representation", "", "").
		Execute()
	if err != nil {
		log.Printf("Failed to create processing job: %v", err)
		// Consider rolling back clip creation or marking clip as failed
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Failed to create processing job: %v", err))
	}
	if err := json.Unmarshal(bodyBytes, &createdJobs); err != nil || len(createdJobs) == 0 {
		log.Printf("Failed to unmarshal created job or empty result: %v. Body: %s", err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Failed to process job creation response")
	}

	// 4. Return a response with the clip ID and job ID
	return utils.RespondWithJSON(c, fiber.StatusAccepted, fiber.Map{
		"clip_id": createdClips[0].ID.String(),
		"job_id":  createdJobs[0].ID.String(),
		"status":  createdClips[0].Status,
		"message": "Clip generation process initiated",
	})
}

// CreateClipPayload defines the expected JSON structure for creating a new clip.
type CreateClipPayload struct {
	SourceVideoID string    `json:"source_video_id"`
	Title         string    `json:"title"`
	Description   *string   `json:"description,omitempty"`
	StartTime     *float64  `json:"start_time,omitempty"`
	EndTime       *float64  `json:"end_time,omitempty"`
	AspectRatio   *string   `json:"aspect_ratio,omitempty"`
	// Add other fields from models.Clip that can be set at creation time
}

// CreateClip handles creating a new clip in a project.
func CreateClip(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid project ID format")
	}
	log.Printf("Received request to create a clip for project ID: %s", projectID)

	var payload CreateClipPayload
	if err := c.BodyParser(&payload); err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, fmt.Sprintf("Cannot parse JSON: %v", err))
	}

	if payload.SourceVideoID == "" || payload.Title == "" {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "SourceVideoID and Title are required")
	}
	sourceVideoUUID, err := uuid.Parse(payload.SourceVideoID)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid SourceVideoID format")
	}

	// Check if SourceVideo exists and belongs to the project using SupabaseClient
	var sourceVideos []models.SourceVideo
	bodyBytes, _, err := config.SupabaseClient.From("source_videos").
		Select("id", "", false).
		Eq("id", sourceVideoUUID.String()).
		Eq("project_id", projectID.String()).
		Execute()
	if err != nil {
		log.Printf("Error fetching source video %s for project %s: %v", sourceVideoUUID, projectID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error verifying source video")
	}
	if err := json.Unmarshal(bodyBytes, &sourceVideos); err != nil || len(sourceVideos) == 0 {
		log.Printf("Source video not found or unmarshal error: %v. Body: %s", err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusNotFound, "Source video not found or does not belong to the project")
	}

	now := time.Now()
	newClipID := uuid.New()

	clip := models.Clip{
		ID:            newClipID,
		ProjectID:     &projectID,
		SourceVideoID: sourceVideoUUID,
		Title:         payload.Title,
		Description:   payload.Description,
		StartTime:     payload.StartTime,
		EndTime:       payload.EndTime,
		AspectRatio:   payload.AspectRatio,
		Status:        "draft",
		CreatedAt:     now,
		UpdatedAt:     now,
	}

	var createdClips []models.Clip
	bodyBytes, _, err = config.SupabaseClient.From("clips").
		Insert(clip, false, "representation", "", "").
		Execute()
	if err != nil {
		log.Printf("Error creating clip for project %s: %v", projectID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not create clip: %v", err))
	}
	if err := json.Unmarshal(bodyBytes, &createdClips); err != nil || len(createdClips) == 0 {
		log.Printf("Error unmarshalling created clip or empty result for project %s: %v. Body: %s", projectID, err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Could not process clip creation response")
	}

	log.Printf("Successfully created clip ID %s for project ID %s", createdClips[0].ID, projectID)
	return utils.RespondWithJSON(c, fiber.StatusCreated, createdClips[0])
}

// GetClip retrieves a specific clip by its ID and project ID.
func GetClip(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	clipIDStr := c.Params("clipId")
	log.Printf("Received request to get clip ID %s for project ID %s", clipIDStr, projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		log.Printf("Invalid project ID format: %s", projectIDStr)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}

	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		log.Printf("Invalid clip ID format: %s", clipIDStr)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid clip ID format"})
	}

	var clips []models.Clip // Supabase client returns a list, even for single record queries by primary key with .Single()

	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Select("", "", false).
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()). // Ensure clip belongs to the specified project
		// .Single(). // Use .Single() if you are sure there's at most one record and want an error if not exactly one. Here, we handle empty results manually.
		Execute()

	if err != nil {
		log.Printf("Error fetching clip %s for project %s from Supabase: %v", clipID, projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
		"status":  "error",
		"message": fmt.Sprintf("Could not retrieve clip: %v", err),
	})
}

	if err := json.Unmarshal(bodyBytes, &clips); err != nil {
		log.Printf("Error unmarshalling clip data for clip %s, project %s: %v", clipID, projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process clip data: %v", err),
		})
	}

	if len(clips) == 0 {
		log.Printf("Clip with ID %s not found for project ID %s", clipID, projectID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": "Clip not found",
		})
	}

	log.Printf("Successfully retrieved clip ID %s for project ID %s", clipID, projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Clip retrieved successfully",
		"data":    clips[0],
	})
}

// UpdateClipPayload defines the structure for the update clip request body.
// Pointers are used to distinguish between omitted fields and zero-value fields.
type UpdateClipPayload struct {
	Title           *string  `json:"title,omitempty"`
	Description     *string  `json:"description,omitempty"`
	StartTime       *float64 `json:"start_time,omitempty"`
	EndTime         *float64 `json:"end_time,omitempty"`
	TemplateID      *string  `json:"template_id,omitempty" validate:"omitempty,uuid"` // Added TemplateID
	AspectRatio     *string  `json:"aspect_ratio,omitempty"`
	Status          *string  `json:"status,omitempty"`
	BRollEnabled    *bool    `json:"b_roll_enabled,omitempty"`
	CaptionsEnabled *bool    `json:"captions_enabled,omitempty"`
}

// UpdateClip handles updating a specific clip.
func UpdateClip(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	clipIDStr := c.Params("clipId")
	log.Printf("Received request to update clip ID %s for project ID %s", clipIDStr, projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid project ID format")
	}
	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid clip ID format")
	}

	var payload UpdateClipPayload
	if err := c.BodyParser(&payload); err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, fmt.Sprintf("Cannot parse JSON: %v", err))
	}

	// Validate TemplateID if provided
	if payload.TemplateID != nil {
		if _, err := uuid.Parse(*payload.TemplateID); err != nil {
			return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid template_id format")
		}
	}

	updateFields := make(map[string]interface{})
	if payload.Title != nil {
		updateFields["title"] = *payload.Title
	}
	if payload.Description != nil {
		updateFields["description"] = *payload.Description
	}
	if payload.StartTime != nil {
		updateFields["start_time"] = *payload.StartTime
	}
	if payload.EndTime != nil {
		updateFields["end_time"] = *payload.EndTime
	}
	if payload.TemplateID != nil {
		updateFields["template_id"] = *payload.TemplateID // Will be UUID string or null
	}
	if payload.AspectRatio != nil {
		updateFields["aspect_ratio"] = *payload.AspectRatio
	}
	if payload.Status != nil {
		updateFields["status"] = *payload.Status
	}
	if payload.BRollEnabled != nil {
		updateFields["b_roll_enabled"] = *payload.BRollEnabled
	}
	if payload.CaptionsEnabled != nil {
		updateFields["captions_enabled"] = *payload.CaptionsEnabled
	}

	if len(updateFields) == 0 {
		// No updatable fields were provided, perhaps return current clip data or 304 Not Modified
		// For now, returning an error or the existing data. Let's fetch and return existing.
		var existingClip []models.Clip
		bodyBytes, _, err := config.SupabaseClient.From("clips").
			Select("*", "", false).
			Eq("id", clipID.String()).
			Eq("project_id", projectID.String()).
			Execute()
		if err != nil || len(bodyBytes) == 0 {
			return utils.RespondWithError(c, fiber.StatusNotFound, "Clip not found or error fetching")
		}
		if err := json.Unmarshal(bodyBytes, &existingClip); err != nil || len(existingClip) == 0 {
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error processing clip data")
		}
		return utils.RespondWithJSON(c, fiber.StatusOK, existingClip[0])
	}

	updateFields["updated_at"] = time.Now()

	var updatedClips []models.Clip
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Update(updateFields, "", "representation").
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()).
		Execute()

	if err != nil {
		log.Printf("Error updating clip %s for project %s: %v", clipID, projectID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not update clip: %v", err))
	}

	if err := json.Unmarshal(bodyBytes, &updatedClips); err != nil {
		log.Printf("Error unmarshalling updated clip data for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Could not process clip update response")
	}

	if len(updatedClips) == 0 {
		log.Printf("Clip with ID %s not found for project ID %s, or no changes made.", clipID, projectID)
		return utils.RespondWithError(c, fiber.StatusNotFound, "Clip not found or no update performed")
	}

	log.Printf("Successfully updated clip ID %s for project ID %s", clipID, projectID)
	return utils.RespondWithJSON(c, fiber.StatusOK, updatedClips[0])
}

// DeleteClip handles deleting a specific clip.
func DeleteClip(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	clipIDStr := c.Params("clipId")
	log.Printf("Received request to delete clip ID %s for project ID %s", clipIDStr, projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}
	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid clip ID format"})
	}

	// Supabase Delete does not directly return the count of deleted rows easily in the Go client's basic execute.
	// To confirm deletion, we might normally fetch before delete, or rely on the operation not erroring
	// if the row doesn't exist matching all Eq conditions (it usually doesn't error, just affects 0 rows).
	// For a robust check, one might count or select before deleting, or check if the client offers a way to get affected rows count.
	// Here, we'll assume a successful execution of Delete without error means it either deleted the item or it wasn't there to begin with under the specified conditions.
	// The `Execute` method for delete in PostgREST (which Supabase uses) might return an empty body or the deleted records based on `Prefer` header.
	// Let's try to get the deleted record back using "representation".

	var results []models.Clip // To capture the potentially returned deleted record
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Delete("", "representation"). // Requesting the deleted record back
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()).
		Execute()

	if err != nil {
		log.Printf("Error deleting clip %s for project %s from Supabase: %v", clipID, projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not delete clip: %v", err),
		})
	}

	// Try to unmarshal the response to see if we got the deleted record back.
	// If `bodyBytes` is empty or not a valid JSON array of clips, unmarshalling might fail or result in an empty `results` slice.
	if len(bodyBytes) > 0 {
		if err := json.Unmarshal(bodyBytes, &results); err != nil {
			// Log this, but it's not necessarily a failure of the delete operation itself
			log.Printf("Warning: could not unmarshal response after delete for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		}
	}

	// If 'results' is empty, it means either the record didn't exist, or Supabase didn't return it.
	// PostgREST typically returns the deleted object(s) if `Prefer: return=representation` is set (which `"representation"` in `Delete` should do).
	// So, an empty result usually means 'not found'.
	if len(results) == 0 {
		log.Printf("Clip with ID %s not found for project ID %s, or already deleted.", clipID, projectID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": "Clip not found or already deleted",
		})
	}

	log.Printf("Successfully deleted clip ID %s for project ID %s", clipID, projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Clip deleted successfully",
		"data":    results[0], // Return the data of the deleted clip
	})
}

// Helper function to get and validate a clip for a specific project
func getValidClipForProject(c *fiber.Ctx, projectIDStr string, clipIDStr string) (*models.Clip, error) {
	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		log.Printf("Invalid project ID format in getValidClipForProject: %s", projectIDStr)
		return nil, fmt.Errorf("invalid project ID format")
	}

	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		log.Printf("Invalid clip ID format in getValidClipForProject: %s", clipIDStr)
		return nil, fmt.Errorf("invalid clip ID format")
	}

	var clips []models.Clip
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Select("*", "", false).
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()).
		Limit(1, "").
		Execute()

	if err != nil {
		log.Printf("Error fetching clip %s for project %s: %v", clipID, projectID, err)
		return nil, fmt.Errorf("error fetching clip: %w", err)
	}

	if err := json.Unmarshal(bodyBytes, &clips); err != nil {
		log.Printf("Error unmarshalling clip data for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		return nil, fmt.Errorf("error processing clip data: %w", err)
	}

	if len(clips) == 0 {
		log.Printf("Clip %s not found or does not belong to project %s", clipID, projectID)
		return nil, fmt.Errorf("clip not found")
	}

	return &clips[0], nil
}

// GetClipDownloadURL generates and returns a signed URL for downloading a processed clip.
// GET /api/v1/projects/:projectId/clips/:clipId/download
func GetClipDownloadURL(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	clipIDStr := c.Params("clipId")

	clip, err := getValidClipForProject(c, projectIDStr, clipIDStr)
	if err != nil {
		switch err.Error() {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, err.Error())
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, err.Error())
		default:
			// Log the original error for internal tracking if it's a fetching/processing error
			if strings.Contains(err.Error(), "error fetching clip") || strings.Contains(err.Error(), "error processing clip data") {
				log.Printf("Internal error in GetClipDownloadURL calling getValidClipForProject: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "Failed to retrieve clip details.")
			}
			// Fallback for any other type of error from the helper not explicitly handled.
			log.Printf("Unexpected error in GetClipDownloadURL calling getValidClipForProject: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred.")
		}
	}

	// TODO: Use a defined constant for status, e.g., models.ClipStatusCompleted
	if clip.Status != "COMPLETED" { // Assuming "COMPLETED" is the status for a processed video
		log.Printf("Clip %s is not yet processed. Current status: %s", clip.ID, clip.Status)
		return utils.RespondWithError(c, fiber.StatusConflict, fmt.Sprintf("Clip is not yet processed. Current status: %s", clip.Status))
	}

	if clip.StoragePath == nil || *clip.StoragePath == "" {
		log.Printf("Clip %s (status: %s) does not have a storage path defined.", clip.ID, clip.Status)
		return utils.RespondWithError(c, fiber.StatusNotFound, "Processed video file path not found for this clip.")
	}

	// Assumed bucket name and expiration time.
	// TODO: Make bucket name and expiration configurable or constants.
	bucketName := "processed_clips"
	expiresIn := 3600 // 1 hour

	signedURL, err := config.SupabaseClient.Storage.CreateSignedUrl(bucketName, *clip.StoragePath, expiresIn)
	if err != nil {
		log.Printf("Error generating signed URL for clip %s (path: %s): %v", clip.ID, *clip.StoragePath, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Failed to generate download URL.")
	}

	log.Printf("Generated download URL for clip %s: %s", clip.ID, signedURL)
	return utils.RespondWithJSON(c, fiber.StatusOK, fiber.Map{"download_url": signedURL})
}
