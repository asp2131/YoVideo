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
	"videothingy/api-gateway/internal/goclient/aiservice"
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
	// Ensure the URL is absolute
	uploadURL := signedUploadURLResponse.Url
	if !strings.HasPrefix(uploadURL, "http") {
		// If the URL doesn't start with http or https, it's a relative URL
		// Prepend the Supabase URL to make it absolute
		supabaseURL := config.GetSupabaseURL()
		if strings.HasPrefix(uploadURL, "/") {
			// If it starts with /, just append to the base URL
			uploadURL = supabaseURL + uploadURL
		} else {
			// Otherwise, add a / between the base URL and the path
			uploadURL = supabaseURL + "/" + uploadURL
		}
	}

	h.Logger.Infof("Successfully generated signed upload URL: %s", uploadURL)

	h.Logger.Infof("Successfully initiated upload for source video ID %s. Upload URL: %s", newSourceVideoID, uploadURL)
	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"status":  "success",
		"message": "Video upload initiated successfully",
		"data": fiber.Map{
			"source_video_id": newSourceVideoID,
			"upload_url":      uploadURL, // The URL client will use to PUT the file
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

// GetVideoTranscription retrieves the transcription for a specific video
func (h *ApplicationHandler) GetVideoTranscription(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	videoIDStr := c.Params("videoId")

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		h.Logger.Errorf("Invalid projectId format: %s, error: %v", projectIDStr, err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid project ID format: %v", err),
		})
	}

	videoID, err := uuid.Parse(videoIDStr)
	if err != nil {
		h.Logger.Errorf("Invalid videoId format: %s, error: %v", videoIDStr, err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid video ID format: %v", err),
		})
	}

	h.Logger.Infof("Fetching transcription for ProjectID: %s, VideoID: %s", projectID.String(), videoID.String())

	// Fetch the video details
	video, err := h.getSourceVideoByIDAndProjectID(c.Context(), videoID, projectID)
	if err != nil {
		if err == ErrRecordNotFound {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
				"status":  "error",
				"message": "Video not found",
			})
		}
		h.Logger.Errorf("Error fetching video details: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to fetch video details",
		})
	}

	// Check if transcription exists
	if video.TranscriptionStatus == nil || *video.TranscriptionStatus != "transcription_completed" {
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "not_found",
			"message": "Transcription not available or not completed",
		})
	}

	// Unmarshal the transcription data
	var transcriptionText string
	if len(video.Transcription) > 0 {
		// The transcription is stored as a JSON-encoded string, so we need to unmarshal it
		if err := json.Unmarshal(video.Transcription, &transcriptionText); err != nil {
			h.Logger.Errorf("Error unmarshaling transcription data: %v", err)
			transcriptionText = "Error: Could not decode transcription"
		}
	}

	// Return the transcription data
	return c.JSON(fiber.Map{
		"status":  "success",
		"message": "Transcription retrieved successfully",
		"data": fiber.Map{
			"video_id":      video.ID,
			"title":         video.Title,
			"status":        video.TranscriptionStatus,
			"transcription": transcriptionText,
			"created_at":    video.CreatedAt,
			"updated_at":    video.UpdatedAt,
		},
	})
}

// updateVideoTranscriptionDetails updates the transcription status, data, and error message for a video.
func (h *ApplicationHandler) updateVideoTranscriptionDetails(ctx context.Context, videoID uuid.UUID, transcriptionStatus string, transcriptionData json.RawMessage, errorMessage string) error {
	updates := map[string]interface{}{
		"transcription_status": transcriptionStatus,
		"updated_at":           time.Now(),
	}

	if transcriptionData != nil {
		updates["transcription"] = transcriptionData
	}

	if errorMessage != "" {
		updates["error_message"] = errorMessage
	}

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

// ListVideos handles the request to list all videos for a specific project.
// It returns a list of videos that belong to the specified project.
func (h *ApplicationHandler) ListVideos(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")

	h.Logger.Infof("Received request to list videos for project ID %s", projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}

	// Check if the project exists
	var projects []models.Project
	body, _, err := h.DB.From("projects").Select("*", "", false).Eq("id", projectID.String()).Execute()
	if err != nil {
		h.Logger.Errorf("Error checking if project %s exists: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to check if project exists"})
	}

	if err := json.Unmarshal(body, &projects); err != nil {
		h.Logger.Errorf("Error unmarshalling project data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to process project data"})
	}

	if len(projects) == 0 {
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"status": "error", "message": "Project not found"})
	}

	// Fetch all videos for the project
	var videos []models.SourceVideo
	body, _, err = h.DB.From("source_videos").Select("*", "", false).Eq("project_id", projectID.String()).Execute()
	if err != nil {
		h.Logger.Errorf("Error fetching videos for project %s: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to fetch videos"})
	}

	if err := json.Unmarshal(body, &videos); err != nil {
		h.Logger.Errorf("Error unmarshalling videos data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to process videos data"})
	}

	h.Logger.Infof("Successfully fetched %d videos for project %s", len(videos), projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Videos retrieved successfully",
		"data":    videos,
	})
}

// DetectVideoHighlights handles the request to detect highlights from a video's transcription.
// It fetches the transcription data, sends it to the AI service for highlight detection,
// and returns the detected highlights.
func (h *ApplicationHandler) DetectVideoHighlights(c *fiber.Ctx) error {
	projectIDStr := c.Params("projectId")
	videoIDStr := c.Params("videoId")

	h.Logger.Infof("Received request to detect highlights for video ID %s in project %s", videoIDStr, projectIDStr)

	projectID, err := uuid.Parse(projectIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid project ID format"})
	}

	videoID, err := uuid.Parse(videoIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid video ID format"})
	}

	// Fetch the source video to ensure it exists and belongs to the project
	video, err := h.getSourceVideoByIDAndProjectID(c.Context(), videoID, projectID)
	if err != nil {
		if errors.Is(err, ErrRecordNotFound) {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"status": "error", "message": "Video not found or does not belong to the specified project"})
		}
		h.Logger.Errorf("Error fetching video %s for project %s: %v", videoID, projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to fetch video details"})
	}

	// Check if the video has been transcribed
	if video.TranscriptionStatus == nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Video transcription status is not available",
		})
	}

	// Check for various completed status formats (COMPLETED, completed, transcription_completed)
	statusText := strings.ToLower(*video.TranscriptionStatus)
	if !strings.Contains(statusText, "complete") {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Video transcription is not complete. Current status: %s", *video.TranscriptionStatus),
		})
	}

	// Parse the transcription data
	var segments []*aiservice.TranscriptSegment

	// First try to parse as JSON
	var transcriptionData models.TranscriptionData
	if err := json.Unmarshal(video.Transcription, &transcriptionData); err != nil {
		// If JSON parsing fails, check if it's a plain text string
		transcriptionText := string(video.Transcription)
		if len(transcriptionText) > 0 && transcriptionText[0] != '{' && transcriptionText[0] != '[' {
			// It's a plain text string, create a single segment with the entire text
			h.Logger.Infof("Using plain text transcription for video %s: %s", videoID, transcriptionText)
			segments = append(segments, &aiservice.TranscriptSegment{
				Text:      transcriptionText,
				StartTime: 0.0,
				EndTime:   60.0, // Assume 60 seconds if we don't know the actual duration
			})
		} else {
			// It's not a plain text string and JSON parsing failed
			h.Logger.Errorf("Error parsing transcription data for video %s: %v", videoID, err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to parse transcription data"})
		}
	} else {
		// JSON parsing succeeded, use the segments from the transcription data
		for _, segment := range transcriptionData.Segments {
			segments = append(segments, &aiservice.TranscriptSegment{
				Text:      segment.Text,
				StartTime: segment.StartTime,
				EndTime:   segment.EndTime,
			})
		}
	}

	// Check if we have any segments to process
	if len(segments) == 0 {
		h.Logger.Warnf("No transcription segments found for video %s", videoID)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "No transcription segments found"})
	}

	// Call the AI service to detect highlights
	highlightsResponse, err := h.AIClient.DetectHighlights(c.Context(), segments)
	if err != nil {
		h.Logger.Errorf("Error detecting highlights for video %s: %v", videoID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to detect highlights"})
	}

	// Convert the highlights to a format suitable for the response
	type HighlightResponse struct {
		Text      string  `json:"text"`
		StartTime float64 `json:"start_time"`
		EndTime   float64 `json:"end_time"`
		Score     float32 `json:"score"`
	}

	var highlightsResult []HighlightResponse
	for _, highlight := range highlightsResponse.GetHighlights() {
		highlightsResult = append(highlightsResult, HighlightResponse{
			Text:      highlight.GetText(),
			StartTime: highlight.GetStartTime(),
			EndTime:   highlight.GetEndTime(),
			Score:     highlight.GetScore(),
		})
	}

	// Store the highlights in the database
	highlightsData, err := json.Marshal(models.HighlightData{
		Highlights: convertToModelHighlights(highlightsResponse.GetHighlights()),
	})
	if err != nil {
		h.Logger.Errorf("Error marshaling highlights data for video %s: %v", videoID, err)
		// Continue with the response even if storing fails
	} else {
		// Update the video record with the highlights data
		updates := map[string]interface{}{
			"highlight_markers": highlightsData,
			"updated_at":        time.Now(),
		}

		_, count, err := h.DB.From("source_videos").
			Update(updates, "", "exact").
			Eq("id", videoID.String()).
			Execute()

		if err != nil {
			h.Logger.Errorf("Error updating highlights for video %s: %v", videoID, err)
			// Continue with the response even if storing fails
		} else if count == 0 {
			h.Logger.Warnf("No rows updated when saving highlights for video %s", videoID)
		}
	}

	h.Logger.Infof("Successfully detected %d highlights for video %s", len(highlightsResult), videoID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":     "success",
		"highlights": highlightsResult,
	})
}

// convertToModelHighlights converts aiservice.Highlight slice to models.Highlight slice
func convertToModelHighlights(highlights []*aiservice.Highlight) []models.Highlight {
	result := make([]models.Highlight, len(highlights))
	for i, h := range highlights {
		result[i] = models.Highlight{
			Text:      h.GetText(),
			StartTime: h.GetStartTime(),
			EndTime:   h.GetEndTime(),
			Score:     h.GetScore(),
		}
	}
	return result
}
