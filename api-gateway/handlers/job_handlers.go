package handlers

import (
	"encoding/json"
	"fmt"
	"log"

	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"
	"videothingy/api-gateway/utils"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// GetJobStatus retrieves the status of a specific processing job.
// GET /api/v1/jobs/:jobId
func GetJobStatus(c *fiber.Ctx) error {
	jobIDStr := c.Params("jobId")
	jobID, err := uuid.Parse(jobIDStr)
	if err != nil {
		log.Printf("Invalid job ID format: %s", jobIDStr)
		return utils.RespondWithError(c, fiber.StatusBadRequest, "Invalid job ID format")
	}

	var jobs []models.ProcessingJob // Supabase client expects a slice
	bodyBytes, _, err := config.SupabaseClient.From("processing_jobs").
		Select("*", "", false).
		Eq("id", jobID.String()).
		Limit(1, ""). // Ensure we only get one job
		Execute()

	if err != nil {
		log.Printf("Error fetching job %s from Supabase: %v", jobID, err)
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not retrieve job status: %v", err))
	}

	if err := json.Unmarshal(bodyBytes, &jobs); err != nil {
		log.Printf("Error unmarshalling job data for job %s: %v. Body: %s", jobID, err, string(bodyBytes))
		return utils.RespondWithError(c, fiber.StatusInternalServerError, fmt.Sprintf("Could not process job data: %v", err))
	}

	if len(jobs) == 0 {
		log.Printf("Job %s not found", jobID)
		return utils.RespondWithError(c, fiber.StatusNotFound, "Job not found")
	}

	job := jobs[0]
	log.Printf("Successfully retrieved status for job ID: %s. Status: %s", jobID, job.Status)
	return utils.RespondWithJSON(c, fiber.StatusOK, job) // Return the full job object
}
