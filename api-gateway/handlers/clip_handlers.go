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

// CreateClipPayload defines the expected JSON structure for creating a clip.
// We use pointers for optional fields to distinguish between a field not provided
// and a field provided with an explicit zero value (e.g. 0 for StartTime).
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
		log.Printf("Invalid project ID format '%s': %v", projectIDStr, err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid project ID format: %s", projectIDStr),
		})
	}
	log.Printf("Received request to create a clip for project ID: %s", projectID)

	payload := new(CreateClipPayload)
	if err := c.BodyParser(payload); err != nil {
		log.Printf("Error parsing create clip payload for project %s: %v", projectID, err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid request body: %v", err),
		})
	}

	// Validate required fields
	if payload.SourceVideoID == "" {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'source_video_id' is required"})
	}
	sourceVideoUUID, err := uuid.Parse(payload.SourceVideoID)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid 'source_video_id' format"})
	}

	if payload.Title == "" {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'title' is required"})
	}

	newClipID := uuid.New()
	now := time.Now()

	clip := models.Clip{
		ID:            newClipID,
		ProjectID:     &projectID, // ProjectID in models.Clip is a pointer
		SourceVideoID: sourceVideoUUID,
		Title:         payload.Title,
		Description:   payload.Description,
		StartTime:     payload.StartTime,
		EndTime:       payload.EndTime,
		AspectRatio:   payload.AspectRatio,
		Status:        "draft", // Default status
		CreatedAt:     now,
		UpdatedAt:     now,
		// Initialize other nullable fields from models.Clip as needed, e.g. BRollEnabled: new(bool) false,
	}

	var results []models.Clip

	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Insert(clip, false, "", "representation", ""). // Corrected: Added upsert (false) and onConflict ("") arguments
		Execute()

	if err != nil {
		log.Printf("Error creating clip for project %s in Supabase: %v", projectID, err)
		// Attempt to parse Supabase error for more specific feedback
		// This is a generic way; Supabase might have specific error structures
		supaErrStr := err.Error()
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not create clip: %s", supaErrStr),
		})
	}

	if err := json.Unmarshal(bodyBytes, &results); err != nil {
		log.Printf("Error unmarshalling created clip data for project %s: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process clip creation response: %v", err),
		})
	}

	if len(results) == 0 {
		log.Printf("Clip creation for project %s did not return data", projectID)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Clip creation failed to return data",
		})
	}

	log.Printf("Successfully created clip with ID %s for project ID %s", results[0].ID, projectID)
	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"status":  "success",
		"message": "Clip created successfully",
		"data":    results[0],
	})
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
	Title            *string  `json:"title,omitempty"`
	Description      *string  `json:"description,omitempty"`
	StartTime        *float64 `json:"start_time,omitempty"`
	EndTime          *float64 `json:"end_time,omitempty"`
	AspectRatio      *string  `json:"aspect_ratio,omitempty"`
	Status           *string  `json:"status,omitempty"`
	BRollEnabled     *bool    `json:"b_roll_enabled,omitempty"`
	CaptionsEnabled  *bool    `json:"captions_enabled,omitempty"`
}

// UpdateClip handles updating a specific clip.
func UpdateClip(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	clipIDStr := c.Params("clipId")
	log.Printf("Received request to update clip ID %s for project ID %s", clipIDStr, projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}
	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid clip ID format"})
	}

	payload := new(UpdateClipPayload)
	if err := c.BodyParser(payload); err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid request body"})
	}

	// Construct a map of fields to update, only including non-nil fields from the payload.
	// This is what Supabase expects for a partial update.
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
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "No update fields provided"})
	}

	// Always update the updated_at timestamp
	updateFields["updated_at"] = time.Now()

	var results []models.Clip
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Update(updateFields, "", "representation"). // Third arg 'returning' for Supabase Go library
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()). // Ensure we only update the clip if it belongs to the project
		Execute()

	if err != nil {
		log.Printf("Error updating clip %s for project %s in Supabase: %v", clipID, projectID, err)
		// Check for specific errors, like not found, if the Supabase client provides them distinctly
		// For now, a general server error is returned.
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not update clip: %v", err),
		})
	}

	if err := json.Unmarshal(bodyBytes, &results); err != nil {
		log.Printf("Error unmarshalling updated clip data for clip %s: %v", clipID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process clip update response: %v", err),
		})
	}

	// The Update operation with 'representation' should return the updated record(s).
	// If the record was not found (due to wrong clipID or projectID), results will be empty.
	if len(results) == 0 {
		log.Printf("Clip with ID %s not found for project ID %s, or no changes made that triggered a return.", clipID, projectID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": "Clip not found or no update performed", // Or a more specific message if possible
		})
	}

	log.Printf("Successfully updated clip ID %s for project ID %s", clipID, projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Clip updated successfully",
		"data":    results[0],
	})
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
