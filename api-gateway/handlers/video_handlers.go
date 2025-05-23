package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"
)

// ErrRecordNotFound is returned when a database record is not found.
var ErrRecordNotFound = errors.New("record not found")

// InitiateUploadRequest defines the expected JSON structure for initiating a video upload.
type InitiateUploadRequest struct {
	FileName    string `json:"file_name" validate:"required"`
	ContentType string `json:"content_type" validate:"required"` // e.g., "video/mp4"
}

var validate = validator.New()

// InitiateVideoUpload handles creating a SourceVideo record and generating a presigned URL for upload.
func (h *ApplicationHandler) InitiateVideoUpload(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	h.Logger.Infof("Received request to initiate video upload for project ID %s", projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}

	payload := new(InitiateUploadRequest)
	if err := c.BodyParser(payload); err != nil {
		h.Logger.Errorf("Error parsing initiate upload payload: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid request body: %v", err),
		})
	}

	if err := validate.Struct(payload); err != nil {
		h.Logger.Errorf("Validation error for initiate upload payload: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Validation failed: %v", err),
		})
	}

	newSourceVideoID := uuid.New()
	now := time.Now()
	fileExtension := filepath.Ext(payload.FileName)
	// storageFileName ensures unique name in storage using the video's new UUID
	storageFileName := fmt.Sprintf("%s%s", newSourceVideoID.String(), fileExtension)
	// storagePath is relative to the bucket root, e.g., {project_id}/{video_uuid_with_extension}
	storagePath := fmt.Sprintf("%s/%s", projectID.String(), storageFileName)

	format := payload.ContentType
	if format == "" && fileExtension != "" {
		// Attempt to infer from extension if content type is not provided
		// This is a basic inference, more robust mapping might be needed for production
		mimeType := "video/" + strings.TrimPrefix(fileExtension, ".")
		switch strings.ToLower(fileExtension) {
		case ".mp4":
			mimeType = "video/mp4"
		case ".mov":
			mimeType = "video/quicktime"
		case ".webm":
			mimeType = "video/webm"
		// Add more cases as needed
		default:
			// Keep generic or log a warning if type is unknown but content type was also empty
			h.Logger.Warnf("Warning: Unknown file extension '%s' and empty content_type for file %s", fileExtension, payload.FileName)
		}
		format = mimeType
	}

	defaultTranscriptionStatus := "pending_transcription"
	sourceVideo := models.SourceVideo{
		ID:                  newSourceVideoID,
		ProjectID:           &projectID,
		Title:               payload.FileName,
		StoragePath:         storagePath,
		Status:              "pending_upload",
		Format:              &format,
		TranscriptionStatus: &defaultTranscriptionStatus,
		CreatedAt:           now,
		UpdatedAt:           now,
	}

	var createdVideoRecord []models.SourceVideo
	bodyBytes, _, err := config.SupabaseClient.From("source_videos").
		Insert(sourceVideo, false, "", "representation", "").
		Execute()

	if err != nil {
		h.Logger.Errorf("Error creating source video record in Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not create source video record: %v", err),
		})
	}

	if err := json.Unmarshal(bodyBytes, &createdVideoRecord); err != nil || len(createdVideoRecord) == 0 {
		h.Logger.Errorf("Error unmarshalling or empty response for source video record creation: %v, body: %s", err, string(bodyBytes))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to confirm source video record creation",
		})
	}

	const supabaseBucketName = "source-videos" // This should match your Supabase bucket name

	// Use CreateSignedUploadURL for generating a URL to upload a new file.
	// func (c *Client) CreateSignedUploadURL(bucketID string, path string) (SignedUploadURLResponse, error)
	// Corrected based on linter: method is CreateSignedUploadUrl (lowercase 'u')
	h.Logger.Infof("Generating signed upload URL for bucket '%s', path '%s'...", supabaseBucketName, storagePath)
	signedUploadURLResponse, err := config.SupabaseClient.Storage.CreateSignedUploadUrl(supabaseBucketName, storagePath)
	if err != nil {
		h.Logger.Errorf("Error generating signed upload URL for bucket '%s', path '%s': %v", supabaseBucketName, storagePath, err)
		// Consider deleting the source_videos record or marking it as failed.
		// For now, we'll try to delete it to keep things clean if upload cannot be initiated.
		deleteErr := h.deleteSourceVideoRecordOnError(newSourceVideoID)
		if deleteErr != nil {
			h.Logger.Errorf("Additionally, failed to delete source video record %s after signed URL error: %v", newSourceVideoID, deleteErr)
		}
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not generate upload URL: %v", err),
		})
	}
	h.Logger.Infof("Successfully generated signed upload URL: %s", signedUploadURLResponse.Url)

	h.Logger.Infof("Successfully initiated upload for source video ID %s. Upload URL: %s", newSourceVideoID, signedUploadURLResponse.Url)
	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"status":  "success",
		"message": "Video upload initiated successfully",
		"data": fiber.Map{
			"source_video_id": newSourceVideoID,
			"upload_url":      signedUploadURLResponse.Url, // The URL client will use to PUT the file
			"method":          "PUT",
			"storage_path":    storagePath, // The eventual path in Supabase storage (relative to bucket)
			"headers": fiber.Map{ // Client should use these headers for the PUT request to the upload_url
				"Content-Type": payload.ContentType,
				// Supabase presigned URLs for upload might also expect specific cache-control or other headers.
				// The token is part of the signedURLResponse.URL itself.
			},
		},
	})
}

// deleteSourceVideoRecordOnError is a helper to attempt cleanup if presigned URL generation fails.
func (h *ApplicationHandler) deleteSourceVideoRecordOnError(videoID uuid.UUID) error {
	h.Logger.Warnf("Attempting to delete source video record %s due to subsequent error.", videoID)
	_, _, err := config.SupabaseClient.From("source_videos").
		Delete("", "").
		Eq("id", videoID.String()).
		Execute()
	if err != nil {
		return fmt.Errorf("failed to delete source video record %s: %w", videoID, err)
	}
	h.Logger.Infof("Successfully deleted source video record %s after error.", videoID)
	return nil
}

// TriggerTranscription handles the request to start transcription for a video.
func (h *ApplicationHandler) TriggerTranscription(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId") // Corrected: camelCase to match route
	videoIDStr := c.Params("videoId")     // Corrected: camelCase to match route

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		h.Logger.Errorf("Invalid projectId format: %s, error: %v", projectIDStr, err) // Log corrected param name
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid project ID format: %v", err),
		})
	}

	videoID, err := uuid.Parse(videoIDStr)
	if err != nil {
		h.Logger.Errorf("Invalid videoId format: %s, error: %v", videoIDStr, err) // Log corrected param name
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid video ID format: %v", err),
		})
	}

	h.Logger.Infof("Attempting to trigger transcription for ProjectID: %s, VideoID: %s", projectID.String(), videoID.String())

	// --- 1. Fetch SourceVideo Details --- 
	video, err := h.getSourceVideoByIDAndProjectID(c.Context(), videoID, projectID)
	if err != nil {
		if err == ErrRecordNotFound { 
			h.Logger.Warnf("Video not found for ProjectID: %s, VideoID: %s", projectID.String(), videoID.String())
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
				"status":  "error",
				"message": "Video not found",
			})
		}
		h.Logger.Errorf("Failed to get source video details for VideoID %s: %v", videoID.String(), err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to retrieve video details",
		})
	}

	if video.StoragePath == "" {
		h.Logger.Errorf("VideoID %s found, but StoragePath is empty. Cannot transcribe.", videoID.String())
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Video storage path is missing, cannot initiate transcription.",
		})
	}

	h.Logger.Infof("Found video: ID=%s, Title=%s, StoragePath=%s", video.ID.String(), video.Title, video.StoragePath)

	// --- 2. Call AI Service to Transcribe Audio ---
	ctx, cancel := context.WithTimeout(c.Context(), 120*time.Second) // 120-second timeout for transcription call
	defer cancel()

	// The AIClient's TranscribeAudio method will construct the necessary gRPC request.
	// We pass the audio URL and a filename/identifier.
	// Using video.Title as originalFilename for now, ensure this is appropriate.
	transcriptionResp, err := h.AIClient.TranscribeAudio(ctx, video.StoragePath, video.Title)
	if err != nil {
		h.Logger.WithFields(logrus.Fields{
			"videoID":   videoID,
			"projectID": projectID,
			"audioURL":  video.StoragePath,
			"error":     err.Error(),
		}).Error("AI service TranscribeAudio call failed")
		// Update video status to indicate transcription failure
		// Assuming updateVideoTranscriptionDetails handles setting status and error message
		if updateErr := h.updateVideoTranscriptionDetails(c.Context(), videoID, "transcription_failed", nil, err.Error()); updateErr != nil {
			h.Logger.WithError(updateErr).Error("Failed to update video status to failed after AI error")
		}
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Failed to transcribe video: AI service error"})
	}

	// Assemble the full transcript from segments
	var fullTranscriptText string
	for _, segment := range transcriptionResp.Segments {
		fullTranscriptText += segment.Text + " " // Add a space between segments
	}
	// Trim trailing space if any
	if len(fullTranscriptText) > 0 {
		fullTranscriptText = fullTranscriptText[:len(fullTranscriptText)-1]
	}

	h.Logger.WithFields(logrus.Fields{
		"videoID":   videoID,
		"projectID": projectID,
		"transcriptLength": len(fullTranscriptText),
	}).Info("Video transcribed successfully by AI service")

	// Update video status to completed and store the transcript
	// Marshal the full transcript text to JSON RawMessage for storing, or adapt the DB model
	transcriptJSON, err := json.Marshal(fullTranscriptText)
	if err != nil {
		h.Logger.WithFields(logrus.Fields{
			"videoID":   videoID,
			"projectID": projectID,
			"error":     err.Error(),
		}).Error("Failed to marshal full transcript text for DB storage")
		// Even if marshalling fails, try to mark as completed but with an error note or empty transcript
		if updateErr := h.updateVideoTranscriptionDetails(c.Context(), videoID, "transcription_completed", nil, "Error marshalling transcript"); updateErr != nil {
			h.Logger.WithError(updateErr).Error("Failed to update video status after transcript marshalling error")
		}
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Failed to process transcript for storage"})
	}

	if err := h.updateVideoTranscriptionDetails(c.Context(), videoID, "transcription_completed", transcriptJSON, ""); err != nil {
		h.Logger.WithError(err).Error("Failed to update video status to complete and store transcript")
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Failed to update video status after transcription"})
	}

	h.Logger.Infof("Successfully initiated and recorded transcription for VideoID: %s", videoID.String())
	return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
		"status":   "success",
		"message":  "Transcription initiated and results stored.", // Or "Transcription processing started"
		"video_id": videoID.String(),
	})
}

// getSourceVideoByIDAndProjectID fetches a source video by its ID and project ID from the database.
func (h *ApplicationHandler) getSourceVideoByIDAndProjectID(ctx context.Context, videoID uuid.UUID, projectID uuid.UUID) (*models.SourceVideo, error) {
	var video models.SourceVideo
	// Using h.DB which is *postgrest.Client
	// Ensure the query filters by both videoID and projectID for security/scoping.
	// The actual Supabase/PostgREST query might look different.
	// This is a conceptual representation.
	_, err := h.DB.From("source_videos").
		Select("*", "exact", false).
		Eq("id", videoID.String()).
		Eq("project_id", projectID.String()). // Ensure video belongs to the project
		Single().
		ExecuteTo(&video)

	if err != nil {
		// Check for specific PostgREST error for not found, e.g., if err contains "PGRST116"
		// For now, a generic error check. This needs refinement based on postgrest-go error handling.
		return nil, ErrRecordNotFound // Using ErrRecordNotFound as a conventional not found error
	}
	return &video, nil
}

// updateVideoTranscriptionDetails updates the transcription status, data, and error message for a video.
func (h *ApplicationHandler) updateVideoTranscriptionDetails(ctx context.Context, videoID uuid.UUID, transcriptionStatus string, transcriptionData json.RawMessage, errorMessage string) error {
	updates := make(map[string]interface{})
	now := time.Now()

	updates["transcription_status"] = transcriptionStatus
	updates["updated_at"] = now

	if transcriptionData != nil && transcriptionStatus == "transcription_completed" {
		updates["transcription"] = transcriptionData // This should be json.RawMessage or compatible
		updates["error_message"] = nil // Clear previous errors if successful
	} else {
		// If not completed or data is nil, ensure transcription field isn't accidentally overwritten with nil if it shouldn't be.
		// Depending on desired behavior, you might want to explicitly set it to nil or not include it in updates.
	}

	if errorMessage != "" {
		updates["error_message"] = errorMessage
	}

	// Using h.DB which is *postgrest.Client
	_, count, err := h.DB.From("source_videos").
		Update(updates, "", "exact"). // Using "exact" to get a count of updated rows
		Eq("id", videoID.String()).
		Execute()

	if err != nil {
		h.Logger.Errorf("DB error in updateVideoTranscriptionDetails for VideoID %s: %v", videoID, err)
		return fmt.Errorf("database update failed: %w", err)
	}
	if count == 0 {
		h.Logger.Warnf("No rows updated in updateVideoTranscriptionDetails for VideoID %s. Video might not exist or match criteria.", videoID)
		return ErrRecordNotFound // Or a more specific error indicating update target not found
	}

	h.Logger.Infof("Successfully updated transcription details for VideoID %s. Status: %s", videoID, transcriptionStatus)
	return nil
}
