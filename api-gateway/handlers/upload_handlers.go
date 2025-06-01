package handlers

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv" // Added strconv
	"time"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// ChunkedUploadHandler handles chunked file uploads for large video files
func (h *ApplicationHandler) ChunkedUploadHandler(c *fiber.Ctx) error {
	videoIDStr := c.Params("videoId")
	videoID, err := uuid.Parse(videoIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Invalid video ID format",
		})
	}

	// Parse multipart form
	_, err = c.MultipartForm()
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to parse multipart form",
		})
	}

	// Get chunk metadata
	chunkNumber := c.FormValue("chunkNumber", "0")
	totalChunks := c.FormValue("totalChunks", "1")
	fileName := c.FormValue("fileName", "")
	
	if fileName == "" {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Missing file name",
		})
	}

	// Get the file chunk
	file, err := c.FormFile("chunk")
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Missing file chunk",
		})
	}

	// Create temp directory for chunks if it doesn't exist
	tempDir := filepath.Join(os.TempDir(), "videothingy-uploads", videoID.String())
	if err := os.MkdirAll(tempDir, 0755); err != nil {
		h.Logger.Errorf("Failed to create temp directory: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to create temp directory",
		})
	}

	// Save chunk to temp file
	chunkPath := filepath.Join(tempDir, fmt.Sprintf("chunk_%s", chunkNumber))
	if err := c.SaveFile(file, chunkPath); err != nil {
		h.Logger.Errorf("Failed to save chunk: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to save chunk",
		})
	}

	// Convert chunkNumber and totalChunks to int
	cn, err := strconv.Atoi(chunkNumber)
	if err != nil {
		h.Logger.Errorf("Invalid chunk number: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid chunk number"})
	}
	tc, err := strconv.Atoi(totalChunks)
	if err != nil {
		h.Logger.Errorf("Invalid total chunks: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "Invalid total chunks"})
	}

	// Validate chunk numbers
	if tc < 1 {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "totalChunks must be at least 1"})
	}
	if cn < 1 || cn > tc {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": fmt.Sprintf("chunkNumber must be between 1 and %d", tc)})
	}

	// If this is the last chunk, combine all chunks and upload
	if cn == tc {
		h.Logger.Infof("Last chunk %d/%d received for video %s, filename %s. Combining chunks...", cn, tc, videoID.String(), fileName)

		// Fetch video record to get storage path and other details
		var videos []models.SourceVideo
		bodyBytes, _, err := h.DB.From("source_videos").
			Select("*", "", false).
			Eq("id", videoID.String()).
			Execute()

		if err != nil {
			h.Logger.Errorf("Error fetching video %s for chunk completion: %v", videoID, err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
				"status":  "error",
				"message": "Failed to fetch video record for chunk completion",
			})
		}

		if err := json.Unmarshal(bodyBytes, &videos); err != nil || len(videos) == 0 {
			h.Logger.Warnf("Video record %s not found for chunk completion", videoID)
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
				"status":  "error",
				"message": "Video not found for chunk completion",
			})
		}
		video := videos[0]

		// Combine chunks
		combinedFilePath := filepath.Join(tempDir, fileName) // Save combined file with original name in tempDir first

		// Remove combined file if it already exists to ensure idempotency of this step
		_ = os.Remove(combinedFilePath) 

		combinedFile, err := os.OpenFile(combinedFilePath, os.O_CREATE|os.O_WRONLY, 0644) // Create fresh, no O_APPEND for initial open
		if err != nil {
			h.Logger.Errorf("Failed to create combined file %s: %v", combinedFilePath, err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to create combined file"})
		}
		defer combinedFile.Close()

		var totalSize int64 = 0
		for i := 1; i <= tc; i++ {
			chunkPartPath := filepath.Join(tempDir, fmt.Sprintf("chunk_%d", i))
			chunkFile, err := os.Open(chunkPartPath)
			if err != nil {
				h.Logger.Errorf("Failed to open chunk %s for combining: %v", chunkPartPath, err)
				// Consider how to handle missing chunks - for now, fail hard
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": fmt.Sprintf("Failed to open chunk %d for combining", i)})
			}
			defer chunkFile.Close()

			written, err := io.Copy(combinedFile, chunkFile)
			if err != nil {
				h.Logger.Errorf("Failed to append chunk %s to combined file: %v", chunkPartPath, err)
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to append chunk to combined file"})
			}
			totalSize += written
			// Optionally, delete chunk after appending: os.Remove(chunkPartPath)
		}
		h.Logger.Infof("Successfully combined %d chunks into %s, total size: %d bytes", tc, combinedFilePath, totalSize)

		// Upload combined file to Supabase (logic adapted from UploadFileHandler)
		finalCombinedFile, err := os.Open(combinedFilePath)
		if err != nil {
			h.Logger.Errorf("Failed to open combined file for upload %s: %v", combinedFilePath, err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to open combined file for upload"})
		}
		defer finalCombinedFile.Close()

		pr, pw := io.Pipe()
		uploadErrChan := make(chan error, 1)

		go func() {
			defer pw.Close()
			_, err := io.Copy(pw, finalCombinedFile)
			if err != nil {
				uploadErrChan <- err
			}
			close(uploadErrChan)
		}()

		supabaseStoragePath := video.StoragePath // Use the storage path from the video record
		supabaseURL := fmt.Sprintf("%s/storage/v1/object/%s", config.GetSupabaseURL(), supabaseStoragePath)

		req, err := http.NewRequest("POST", supabaseURL, pr)
		if err != nil {
			h.Logger.Errorf("Error creating Supabase upload request for combined file: %v", err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to create upload request for combined file"})
		}

		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", config.GetSupabaseKey()))
		req.Header.Set("Content-Type", "application/octet-stream") // Or derive from fileName
		req.ContentLength = totalSize

		client := &http.Client{Timeout: 60 * time.Minute} // Increased timeout for potentially very large combined files
		supResp, err := client.Do(req)
		if err != nil {
			h.Logger.Errorf("Error uploading combined file to Supabase: %v", err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to upload combined file to storage"})
		}
		defer supResp.Body.Close()

		select {
		case err := <-uploadErrChan:
			if err != nil {
				h.Logger.Errorf("Error streaming combined file: %v", err)
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Failed to stream combined file"})
			}
		default:
		}

		if supResp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(supResp.Body) // Changed tbody to bodyBytes for clarity and to avoid conflict if 'body' was used elsewhere
			h.Logger.Errorf("Supabase upload failed for combined file: %s", string(bodyBytes))
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"status": "error", "message": "Supabase upload failed for combined file"})
		}

		// Update video status in database
		updates := map[string]interface{}{
			"status":      "uploaded", // Used string literal "uploaded"
			"file_size":   totalSize,
			"updated_at":  time.Now(),
		}
		_, _, err = h.DB.From("source_videos").
			Update(updates, "", "").
			Eq("id", videoID.String()).
			Execute()

		if err != nil {
			h.Logger.Errorf("Error updating video status after chunked upload for %s: %v", videoID, err)
			// Don't fail the request if DB update fails, as file is uploaded
		}

		// Cleanup: Remove the temporary directory for this video's chunks
		if err := os.RemoveAll(tempDir); err != nil {
			h.Logger.Warnf("Failed to remove temp directory %s after chunk processing: %v", tempDir, err)
		}

		h.Logger.Infof("Successfully processed and uploaded all chunks for video %s", videoID)
		return c.Status(fiber.StatusOK).JSON(fiber.Map{
			"status":    "success",
			"message":   "All chunks uploaded and file processed successfully",
			"video_id":  videoID.String(),
			"file_name": fileName,
			"total_size": totalSize,
		})
	}



	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Chunk uploaded successfully",
		"chunk":   chunkNumber,
		"total":   totalChunks,
	})
}

// UploadFileHandler handles direct file upload with streaming support
func (h *ApplicationHandler) UploadFileHandler(c *fiber.Ctx) error {
	videoIDStr := c.Params("videoId")
	videoID, err := uuid.Parse(videoIDStr)
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "Invalid video ID format",
		})
	}

	// Get the uploaded file
	file, err := c.FormFile("file")
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": "No file uploaded",
		})
	}

	// Fetch video record to get storage path
	var videos []models.SourceVideo
	bodyBytes, _, err := h.DB.From("source_videos").
		Select("*", "", false).
		Eq("id", videoID.String()).
		Execute()

	if err != nil {
		h.Logger.Errorf("Error fetching video %s: %v", videoID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to fetch video record",
		})
	}

	if err := json.Unmarshal(bodyBytes, &videos); err != nil || len(videos) == 0 {
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": "Video not found",
		})
	}

	video := videos[0]

	// Open the uploaded file
	fileHandle, err := file.Open()
	if err != nil {
		h.Logger.Errorf("Error opening uploaded file: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to open uploaded file",
		})
	}
	defer fileHandle.Close()

	// Create a pipe for streaming
	pr, pw := io.Pipe()
	
	// Stream the file to Supabase in a goroutine
	uploadErr := make(chan error, 1)
	go func() {
		defer pw.Close()
		_, err := io.Copy(pw, fileHandle)
		if err != nil {
			uploadErr <- err
		}
		close(uploadErr)
	}()

	// Prepare Supabase storage URL
	supabaseURL := fmt.Sprintf("%s/storage/v1/object/%s", config.GetSupabaseURL(), video.StoragePath)
	
	// Create request with the pipe reader
	req, err := http.NewRequest("POST", supabaseURL, pr)
	if err != nil {
		h.Logger.Errorf("Error creating request: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to create upload request",
		})
	}

	// Set headers
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", config.GetSupabaseKey()))
	req.Header.Set("Content-Type", "application/octet-stream")
	req.ContentLength = file.Size

	// Execute the request
	client := &http.Client{Timeout: 30 * time.Minute} // 30 min timeout for large files
	resp, err := client.Do(req)
	if err != nil {
		h.Logger.Errorf("Error uploading to Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to upload file to storage",
		})
	}
	defer resp.Body.Close()

	// Check for upload errors
	select {
	case err := <-uploadErr:
		if err != nil {
			h.Logger.Errorf("Error streaming file: %v", err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
				"status":  "error",
				"message": "Failed to stream file",
			})
		}
	default:
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		h.Logger.Errorf("Supabase upload failed: %s", string(body))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to upload file to storage",
		})
	}

	// Update video status to 'uploaded'
	updates := map[string]interface{}{
		"status":      "uploaded",
		"file_size":   file.Size,
		"updated_at":  time.Now(),
	}

	_, _, err = h.DB.From("source_videos").
		Update(updates, "", "").
		Eq("id", videoID.String()).
		Execute()

	if err != nil {
		h.Logger.Errorf("Error updating video status: %v", err)
		// Don't fail the request, file was uploaded successfully
	}

	h.Logger.Infof("Successfully uploaded file for video %s", videoID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "File uploaded successfully",
		"video_id": videoID.String(),
	})
}
