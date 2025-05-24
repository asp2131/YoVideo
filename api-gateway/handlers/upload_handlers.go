package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"

	"github.com/gofiber/fiber/v2"

	"videothingy/api-gateway/config"
)

// UploadFileHandler handles file uploads through the API Gateway to avoid CORS issues
func (h *ApplicationHandler) UploadFileHandler(c *fiber.Ctx) error {
	projectID := c.Params("projectId")
	videoID := c.Params("videoId")
	
	h.Logger.Infof("Received file upload request for project %s, video %s", projectID, videoID)
	
	// Get the file from the request
	file, err := c.FormFile("file")
	if err != nil {
		h.Logger.Errorf("Error getting file from request: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error getting file: %v", err),
		})
	}
	
	// Open the file
	fileHandle, err := file.Open()
	if err != nil {
		h.Logger.Errorf("Error opening file: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error opening file: %v", err),
		})
	}
	defer fileHandle.Close()
	
	// Read the file content
	fileContent, err := io.ReadAll(fileHandle)
	if err != nil {
		h.Logger.Errorf("Error reading file content: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error reading file: %v", err),
		})
	}
	
	// Get the storage path from the database
	var videos []map[string]interface{}
	body, _, err := h.DB.From("source_videos").
		Select("storage_path", "", false).
		Eq("id", videoID).
		Execute()
	
	if err != nil {
		h.Logger.Errorf("Error fetching video storage path: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error fetching video details: %v", err),
		})
	}
	
	if err := json.Unmarshal(body, &videos); err != nil {
		h.Logger.Errorf("Error unmarshalling video data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error processing video data: %v", err),
		})
	}
	
	if len(videos) == 0 {
		h.Logger.Errorf("Video with ID %s not found", videoID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Video with ID %s not found", videoID),
		})
	}
	
	storagePath, ok := videos[0]["storage_path"].(string)
	if !ok {
		h.Logger.Errorf("Invalid storage path for video %s", videoID)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Invalid storage path",
		})
	}
	
	// Upload the file to Supabase storage directly using the Supabase client
	const bucketName = "source-videos"
	// Create a request to upload the file
	req, err := http.NewRequest("POST", fmt.Sprintf("%s/storage/v1/object/%s/%s", config.GetSupabaseURL(), bucketName, storagePath), bytes.NewReader(fileContent))
	if err != nil {
		h.Logger.Errorf("Error creating upload request: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error creating upload request: %v", err),
		})
	}
	
	// Set headers
	req.Header.Set("Content-Type", file.Header["Content-Type"][0])
	req.Header.Set("Authorization", "Bearer " + config.GetSupabaseKey())
	
	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		h.Logger.Errorf("Error uploading file to Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Error uploading file: %v", err),
		})
	}
	defer resp.Body.Close()
	
	// Check response status
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		respBody, _ := ioutil.ReadAll(resp.Body)
		h.Logger.Errorf("Supabase upload failed with status %d: %s", resp.StatusCode, string(respBody))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Upload failed with status %d", resp.StatusCode),
		})
	}
	
	// Update the video status to "uploaded"
	_, _, err = h.DB.From("source_videos").
		Update(map[string]interface{}{"status": "uploaded"}, "", "").
		Eq("id", videoID).
		Execute()
	
	if err != nil {
		h.Logger.Errorf("Error updating video status: %v", err)
		// Don't return an error here, as the upload was successful
		// Just log the error and continue
	}
	
	h.Logger.Infof("Successfully uploaded file for video %s", videoID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "File uploaded successfully",
	})
}
