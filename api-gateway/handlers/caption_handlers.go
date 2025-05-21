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
	"github.com/supabase-community/postgrest-go" // Import for postgrest.OrderOpts
)

// CreateCaptionPayload defines the structure for creating a new caption.
// ClipID will be taken from the URL path, not the payload.
type CreateCaptionPayload struct {
	StartTime float64 `json:"start_time" validate:"required,gte=0"`
	EndTime   float64 `json:"end_time" validate:"required,gtfield=StartTime"`
	Text      string  `json:"text" validate:"required"`
	Speaker   *string `json:"speaker,omitempty"`
	IsEdited  *bool   `json:"is_edited,omitempty"`
}

// UpdateCaptionPayload defines the structure for updating an existing caption.
type UpdateCaptionPayload struct {
	StartTime *float64 `json:"start_time,omitempty" validate:"omitempty,gte=0"`
	EndTime   *float64 `json:"end_time,omitempty" validate:"omitempty,gtfield=StartTime"`
	Text      *string  `json:"text,omitempty"`
	Speaker   *string  `json:"speaker,omitempty"`
	IsEdited  *bool    `json:"is_edited,omitempty"`
}

// Helper function to check if a clip exists and belongs to the project.
// Returns the clip if found, or an error.
func getClipForProject(c *fiber.Ctx, projectIDStr, clipIDStr string) (uuid.UUID, uuid.UUID, error) {
	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return uuid.Nil, uuid.Nil, fmt.Errorf("invalid project ID format")
	}
	clipID, err := uuid.Parse(clipIDStr)
	if err != nil {
		return uuid.Nil, uuid.Nil, fmt.Errorf("invalid clip ID format")
	}

	var clips []models.Clip
	bodyBytes, _, err := config.SupabaseClient.From("clips").
		Select("*", "", false).
		Eq("id", clipID.String()).
		Eq("project_id", projectID.String()).
		Execute()

	if err != nil {
		log.Printf("Error fetching clip %s for project %s: %v", clipID, projectID, err)
		return uuid.Nil, uuid.Nil, fmt.Errorf("error fetching clip: %w", err)
	}

	if err := json.Unmarshal(bodyBytes, &clips); err != nil {
		log.Printf("Error unmarshalling clip data for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		return uuid.Nil, uuid.Nil, fmt.Errorf("error processing clip data: %w", err)
	}

	if len(clips) == 0 {
		return uuid.Nil, uuid.Nil, fmt.Errorf("clip not found")
	}
	return projectID, clipID, nil
}

// CreateCaption adds a new caption to a specific clip.
// POST /api/v1/projects/:projectId/clips/:clipId/captions
func CreateCaption(c *fiber.Ctx) error {
	projectIDParam := c.Params("projectId")
	clipIDParam := c.Params("clipId")

	_, clipID, err := getClipForProject(c, projectIDParam, clipIDParam)
	if err != nil {
		errMsg := err.Error()
		switch errMsg {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, errMsg)
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, errMsg)
		default:
			// Check for wrapped errors for internal issues
			if strings.HasPrefix(errMsg, "error fetching clip:") || strings.HasPrefix(errMsg, "error processing clip data:") {
				log.Printf("Internal error from getClipForProject in CreateCaption: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal error occurred while verifying the clip.")
			}
			log.Printf("Unexpected error from getClipForProject in CreateCaption: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred while verifying project/clip.")
		}
	}

	var payload CreateCaptionPayload
	if err := c.BodyParser(&payload); err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, fmt.Sprintf("Cannot parse JSON: %v", err))
	}

	validate := validator.New()
	if err := validate.Struct(payload); err != nil {
		errors := utils.FormatValidationErrors(err)
		return utils.RespondWithError(c, fiber.StatusBadRequest, strings.Join(errors, ", "))
	}

	now := time.Now()
	newCaptionID := uuid.New()

	caption := models.Caption{
		ID:        newCaptionID,
		ClipID:    clipID,
		StartTime: payload.StartTime,
		EndTime:   payload.EndTime,
		Text:      payload.Text,
		Speaker:   payload.Speaker,
		IsEdited:  payload.IsEdited,
		CreatedAt: now,
		UpdatedAt: now,
	}

	var createdCaptions []models.Caption
	bodyBytes, _, err := config.SupabaseClient.From("captions").
		Insert(caption, false, "representation", "", "").
		Execute()

	if err != nil {
		log.Printf("Error creating caption for clip %s: %v", clipID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not create caption: %v", err))
	}

	if err := json.Unmarshal(bodyBytes, &createdCaptions); err != nil || len(createdCaptions) == 0 {
		log.Printf("Error unmarshalling created caption or empty result for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Could not process caption creation response")
	}

	log.Printf("Successfully created caption ID %s for clip ID %s", createdCaptions[0].ID, clipID)
	return utils.RespondWithJSON(c, fiber.StatusCreated, createdCaptions[0])
}

// ListCaptions retrieves all captions for a specific clip.
// GET /api/v1/projects/:projectId/clips/:clipId/captions
func ListCaptions(c *fiber.Ctx) error {
	projectIDParam := c.Params("projectId")
	clipIDParam := c.Params("clipId")

	projectID, clipID, err := getClipForProject(c, projectIDParam, clipIDParam)
	if err != nil {
		errMsg := err.Error()
		switch errMsg {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, errMsg)
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, errMsg)
		default:
			// Check for wrapped errors for internal issues
			if strings.HasPrefix(errMsg, "error fetching clip:") || strings.HasPrefix(errMsg, "error processing clip data:") {
				log.Printf("Internal error from getClipForProject in ListCaptions: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal error occurred while verifying the clip.")
			}
			log.Printf("Unexpected error from getClipForProject in ListCaptions: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred while verifying project/clip.")
		}
	}

	log.Printf("Listing captions for project %s, clip %s", projectID, clipID)

	var captions []models.Caption
	bodyBytes, _, err := config.SupabaseClient.From("captions").
		Select("*", "", false).
		Eq("clip_id", clipID.String()).
		Order("start_time", &postgrest.OrderOpts{Ascending: true}). // Corrected to use postgrest.OrderOpts
		Execute()

	if err != nil {
		log.Printf("Error fetching captions for clip %s: %v", clipID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not retrieve captions: %v", err))
	}

	if err := json.Unmarshal(bodyBytes, &captions); err != nil {
		log.Printf("Error unmarshalling captions for clip %s: %v. Body: %s", clipID, err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Could not process captions data")
	}

	if captions == nil { // Ensure we return an empty list instead of nil if no captions found
		captions = []models.Caption{}
	}

	return utils.RespondWithJSON(c, fiber.StatusOK, captions)
}

// GetCaption retrieves a specific caption by its ID.
// GET /api/v1/projects/:projectId/clips/:clipId/captions/:captionId
func GetCaption(c *fiber.Ctx) error {
	projectIDParam := c.Params("projectId")
	clipIDParam := c.Params("clipId")
	captionIDParam := c.Params("captionId")

	// Validate project and clip existence and ownership
	_, clipID, err := getClipForProject(c, projectIDParam, clipIDParam)
	if err != nil {
		errMsg := err.Error()
		switch errMsg {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, errMsg)
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, errMsg) // Clip itself not found or doesn't belong to project
		default:
			if strings.HasPrefix(errMsg, "error fetching clip:") || strings.HasPrefix(errMsg, "error processing clip data:") {
				log.Printf("Internal error from getClipForProject in GetCaption: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal error occurred while verifying the clip.")
			}
			log.Printf("Unexpected error from getClipForProject in GetCaption: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred while verifying project/clip.")
		}
	}

	capID, err := uuid.Parse(captionIDParam)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid caption ID format")
	}

	log.Printf("Fetching caption %s for clip %s", capID, clipID)

	var caption models.Caption
	bodyBytes, _, err := config.SupabaseClient.From("captions").
		Select("*", "", false).
		Eq("id", capID.String()).
		Eq("clip_id", clipID.String()). // Ensure caption belongs to the validated clip
		Single().                       // Expect a single record
		Execute()

	if err != nil {
		// Check if the error indicates that no rows were found, which PostgREST might return as a non-2xx status
		// or a specific error message. For Single(), if no row is found, it might result in an error.
		// Supabase/Postgrest might return an error if Single() finds no rows, or http error status like 406 Not Acceptable if 0 rows returned for single().
		// We need to be careful how to interpret this. A more robust way might be to not use Single() and check length of slice.
		log.Printf("Error fetching caption %s for clip %s: %v. Body: %s", capID, clipID, err, string(bodyBytes))
		// A common error from PostgREST for Single() when no rows are found could be a specific error string or an empty bodyBytes.
		// If using Single(), an error is returned if zero or more than one row is found.
		// For now, we'll assume any error here means it's either not found or another DB issue.
		return utils.RespondWithError(c, fiber.StatusNotFound, "Caption not found or database error")
	}

	if err := json.Unmarshal(bodyBytes, &caption); err != nil {
		log.Printf("Error unmarshalling caption data for caption %s: %v", capID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error processing caption data")
	}

	// If bodyBytes is empty and no error, it could also mean not found with some client configurations,
	// but Single() should error out. If caption.ID is still Zero after Unmarshal and no error, means not found.
	if caption.ID == uuid.Nil {
        log.Printf("Caption %s for clip %s parsed but ID is nil, likely not found.", capID, clipID)
        return utils.RespondWithError(c, fiber.StatusNotFound, "Caption not found")
    }

	return c.Status(fiber.StatusOK).JSON(caption)
}

// UpdateCaption updates an existing caption.
// PATCH /api/v1/projects/:projectId/clips/:clipId/captions/:captionId
func UpdateCaption(c *fiber.Ctx) error {
	projectIDParam := c.Params("projectId")
	clipIDParam := c.Params("clipId")
	captionIDParam := c.Params("captionId")

	// Validate project and clip existence and ownership
	_, clipID, err := getClipForProject(c, projectIDParam, clipIDParam)
	if err != nil {
		errMsg := err.Error()
		switch errMsg {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, errMsg)
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, errMsg)
		default:
			if strings.HasPrefix(errMsg, "error fetching clip:") || strings.HasPrefix(errMsg, "error processing clip data:") {
				log.Printf("Internal error from getClipForProject in UpdateCaption: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal error occurred while verifying the clip.")
			}
			log.Printf("Unexpected error from getClipForProject in UpdateCaption: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred while verifying project/clip.")
		}
	}

	capID, err := uuid.Parse(captionIDParam)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid caption ID format")
	}

	// Fetch existing caption first
	var existingCaption models.Caption
	existingBodyBytes, _, err := config.SupabaseClient.From("captions").
		Select("*", "", false).
		Eq("id", capID.String()).
		Eq("clip_id", clipID.String()).
		Single().
		Execute()

	if err != nil {
		log.Printf("Error fetching existing caption %s for update: %v", capID, err)
		return utils.RespondWithError(c, fiber.StatusNotFound, "Caption not found or database error during pre-update fetch")
	}
	if err := json.Unmarshal(existingBodyBytes, &existingCaption); err != nil {
		log.Printf("Error unmarshalling existing caption data for caption %s: %v", capID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error processing existing caption data")
	}
	if existingCaption.ID == uuid.Nil {
		return utils.RespondWithError(c, fiber.StatusNotFound, "Caption to update not found")
	}

	payload := new(UpdateCaptionPayload)
	if err := c.BodyParser(payload); err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, fmt.Sprintf("Invalid request payload: %s", err.Error()))
	}

	validate := validator.New()
	if err := validate.Struct(payload); err != nil {
		validationErrors := utils.FormatValidationErrors(err.(validator.ValidationErrors))
		return utils.RespondWithError(c, fiber.StatusBadRequest, strings.Join(validationErrors, ", "))
	}

	updateData := make(map[string]interface{})
	newStartTime := existingCaption.StartTime
	newEndTime := existingCaption.EndTime

	if payload.StartTime != nil {
		updateData["start_time"] = *payload.StartTime
		newStartTime = *payload.StartTime
	}
	if payload.EndTime != nil {
		updateData["end_time"] = *payload.EndTime
		newEndTime = *payload.EndTime
	}

	// Validate times: end_time must be greater than start_time
	if newEndTime <= newStartTime {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "End time must be greater than start time")
	}

	if payload.Text != nil {
		updateData["text"] = *payload.Text
	}
	if payload.Speaker != nil {
		updateData["speaker"] = *payload.Speaker
	}
	if payload.IsEdited != nil {
		updateData["is_edited"] = *payload.IsEdited
	}

	if len(updateData) == 0 {
		// No fields to update, return the existing caption
		return c.Status(fiber.StatusOK).JSON(existingCaption)
	}

	updateData["updated_at"] = time.Now() // Explicitly set updated_at

	log.Printf("Updating caption %s for clip %s with data: %+v", capID, clipID, updateData)

	var updatedCaption models.Caption
	updatedBodyBytes, _, err := config.SupabaseClient.From("captions").
		Update(updateData, "", "representation"). // Use "representation" to get the updated row back
		Eq("id", capID.String()).
		Eq("clip_id", clipID.String()).
		Single(). // Ensure we are updating and returning a single row
		Execute()

	if err != nil {
		log.Printf("Error updating caption %s: %v. Body: %s", capID, err, string(updatedBodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error updating caption")
	}

	if err := json.Unmarshal(updatedBodyBytes, &updatedCaption); err != nil {
		log.Printf("Error unmarshalling updated caption data for caption %s: %v", capID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error processing updated caption data")
	}

	if updatedCaption.ID == uuid.Nil {
        log.Printf("Updated caption %s for clip %s parsed but ID is nil, update might have failed silently or record not returned.", capID, clipID)
        return utils.RespondWithError(c, fiber.StatusInternalServerError, "Failed to retrieve caption after update")
    }

	return c.Status(fiber.StatusOK).JSON(updatedCaption)
}

// DeleteCaption deletes a specific caption.
// DELETE /api/v1/projects/:projectId/clips/:clipId/captions/:captionId
func DeleteCaption(c *fiber.Ctx) error {
	projectIDParam := c.Params("projectId")
	clipIDParam := c.Params("clipId")
	captionIDParam := c.Params("captionId")

	// Validate project and clip existence and ownership
	_, clipID, err := getClipForProject(c, projectIDParam, clipIDParam)
	if err != nil {
		errMsg := err.Error()
		switch errMsg {
		case "invalid project ID format", "invalid clip ID format":
			return utils.RespondWithError(c, fiber.StatusBadRequest, errMsg)
		case "clip not found":
			return utils.RespondWithError(c, fiber.StatusNotFound, errMsg) // Clip itself not found or doesn't belong to project
		default:
			if strings.HasPrefix(errMsg, "error fetching clip:") || strings.HasPrefix(errMsg, "error processing clip data:") {
				log.Printf("Internal error from getClipForProject in DeleteCaption: %v", err)
				return utils.RespondWithError(c, fiber.StatusInternalServerError, "An internal error occurred while verifying the clip.")
			}
			log.Printf("Unexpected error from getClipForProject in DeleteCaption: %v", err)
			return utils.RespondWithError(c, fiber.StatusInternalServerError, "An unexpected error occurred while verifying project/clip.")
		}
	}

	capID, err := uuid.Parse(captionIDParam)
	if err != nil {
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid caption ID format")
	}

	log.Printf("Attempting to delete caption %s for clip %s", capID, clipID)

	// We need to check if the caption exists and belongs to the clip before deleting, 
	// or rely on the DELETE operation's affected rows count if the DB driver/client provides it directly.
	// PostgREST delete with count option can tell us if rows were deleted.
	// Using "minimal" for returning preference as we don't need the deleted row back.
	// The `Execute` method for postgrest-go client returns bodyBytes, count, error.
	// The count should be helpful here.

	_, count, err := config.SupabaseClient.From("captions").
		Delete("minimal", "exact"). // "exact" count should give number of rows deleted.
		Eq("id", capID.String()).
		Eq("clip_id", clipID.String()).
		Execute()

	if err != nil {
		// This error could be a general DB error, or PostgREST might return specific errors for constraint violations etc.
		log.Printf("Error deleting caption %s for clip %s: %v", capID, clipID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, "Error deleting caption")
	}

	if count == 0 {
		log.Printf("Caption %s not found for clip %s, or already deleted. No rows affected.", capID, clipID)
		return utils.RespondWithError(c, fiber.StatusNotFound, "Caption not found")
	}

	log.Printf("Successfully deleted caption %s for clip %s. Rows affected: %d", capID, clipID, count)
	return c.SendStatus(fiber.StatusNoContent)
}
