package handlers

import (
	"encoding/json"
	"fmt"
	"log"
	"path/filepath"
	"strings"
	"time"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// InitiateUploadRequest defines the expected JSON structure for initiating a video upload.
type InitiateUploadRequest struct {
	FileName    string `json:"file_name" validate:"required"`
	ContentType string `json:"content_type" validate:"required"` // e.g., "video/mp4"
}

var validate = validator.New()

// InitiateVideoUpload handles creating a SourceVideo record and generating a presigned URL for upload.
func InitiateVideoUpload(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	log.Printf("Received request to initiate video upload for project ID %s", projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}

	payload := new(InitiateUploadRequest)
	if err := c.BodyParser(payload); err != nil {
		log.Printf("Error parsing initiate upload payload: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid request body: %v", err),
		})
	}

	if err := validate.Struct(payload); err != nil {
		log.Printf("Validation error for initiate upload payload: %v", err)
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
			log.Printf("Warning: Unknown file extension '%s' and empty content_type for file %s", fileExtension, payload.FileName)
		}
		format = mimeType
	}

	defaultTranscriptionStatus := "not_started"
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
		log.Printf("Error creating source video record in Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not create source video record: %v", err),
		})
	}

	if err := json.Unmarshal(bodyBytes, &createdVideoRecord); err != nil || len(createdVideoRecord) == 0 {
		log.Printf("Error unmarshalling or empty response for source video record creation: %v, body: %s", err, string(bodyBytes))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to confirm source video record creation",
		})
	}

	const supabaseBucketName = "source-videos" // This should match your Supabase bucket name

	// Use CreateSignedUploadURL for generating a URL to upload a new file.
	// func (c *Client) CreateSignedUploadURL(bucketID string, path string) (SignedUploadURLResponse, error)
	// Corrected based on linter: method is CreateSignedUploadUrl (lowercase 'u')
	signedUploadURLResponse, err := config.SupabaseClient.Storage.CreateSignedUploadUrl(supabaseBucketName, storagePath)
	if err != nil {
		log.Printf("Error generating signed upload URL for bucket '%s', path '%s': %v", supabaseBucketName, storagePath, err)
		// Consider deleting the source_videos record or marking it as failed.
		// For now, we'll try to delete it to keep things clean if upload cannot be initiated.
		deleteErr := deleteSourceVideoRecordOnError(newSourceVideoID)
		if deleteErr != nil {
			log.Printf("Additionally, failed to delete source video record %s after signed URL error: %v", newSourceVideoID, deleteErr)
		}
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not generate upload URL: %v", err),
		})
	}

	log.Printf("Successfully initiated upload for source video ID %s. Upload URL: %s", newSourceVideoID, signedUploadURLResponse.Url)
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
func deleteSourceVideoRecordOnError(videoID uuid.UUID) error {
	log.Printf("Attempting to delete source video record %s due to subsequent error.", videoID)
	_, _, err := config.SupabaseClient.From("source_videos").
		Delete("", "").
		Eq("id", videoID.String()).
		Execute()
	if err != nil {
		return fmt.Errorf("failed to delete source video record %s: %w", videoID, err)
	}
	log.Printf("Successfully deleted source video record %s after error.", videoID)
	return nil
}
