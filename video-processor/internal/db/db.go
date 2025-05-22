package db

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/google/uuid" // Added for generating Job IDs
	postgrest "github.com/supabase-community/postgrest-go"
)

var client *postgrest.Client

// VideoJobStatus maps to the video_job_statuses table in Supabase.
// We use pointers for fields that can be null (e.g., OutputDetails, ErrorMessage)
// and `json.RawMessage` for JSONB fields to handle them as raw JSON strings initially.
// `omitempty` is used to avoid sending null fields during insertion if they are not set.
type VideoJobStatus struct {
	JobID         string          `json:"job_id"`
	JobType       string          `json:"job_type"`
	Status        string          `json:"status"` // PENDING, PROCESSING, COMPLETED, FAILED
	InputPayload  json.RawMessage `json:"input_payload,omitempty"`
	OutputDetails json.RawMessage `json:"output_details,omitempty"`
	ErrorMessage  *string         `json:"error_message,omitempty"`
	CreatedAt     time.Time       `json:"created_at,omitempty"`
	UpdatedAt     time.Time       `json:"updated_at,omitempty"`
}

const jobStatusTable = "video_job_statuses"

// InitSupabaseClient initializes the Supabase client using environment variables.
func InitSupabaseClient() error {
	supabaseURL := os.Getenv("SUPABASE_URL")
	supabaseKey := os.Getenv("SUPABASE_SERVICE_KEY")

	if supabaseURL == "" || supabaseKey == "" {
		return fmt.Errorf("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
	}

	client = postgrest.NewClient(supabaseURL+"/rest/v1", "", map[string]string{ // Added /rest/v1 to the URL
		"apikey":        supabaseKey,
		"Authorization": fmt.Sprintf("Bearer %s", supabaseKey),
	})

	if client.ClientError != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", client.ClientError)
	}

	log.Println("Supabase client initialized successfully.")
	return nil
}

// GetClient returns the initialized Supabase client.
// It's the caller's responsibility to ensure InitSupabaseClient has been called successfully.
func GetClient() *postgrest.Client {
	if client == nil {
		// This could be a fatal error in a real app, or InitSupabaseClient could be called here.
		// For now, just log and return nil, expecting Init to be called from main.
		log.Println("Warning: Supabase client requested before initialization or after failed initialization.")
	}
	return client
}

// CreateJobRecord creates a new job record in the database with a generated JobID.
// It returns the generated JobID or an error.
func CreateJobRecord(jobType string, inputPayload interface{}) (string, error) {
	if client == nil {
		return "", fmt.Errorf("Supabase client not initialized")
	}

	jobID := uuid.NewString()

	payloadBytes, err := json.Marshal(inputPayload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal input payload: %w", err)
	}

	newRecord := VideoJobStatus{
		JobID:        jobID,
		JobType:      jobType,
		Status:       "PENDING", // Initial status
		InputPayload: payloadBytes,
		// CreatedAt and UpdatedAt are set by default by the DB
	}

	var results []VideoJobStatus // To capture the inserted record if needed, though PostgREST returns it
	// The `Prefer: return=representation` header makes PostgREST return the inserted row(s).
	// Corrected: ExecuteTo returns (interface{}, error). We use _ to ignore the first.
	_, err = client.From(jobStatusTable).Insert(newRecord, false, "representation", "", "").ExecuteTo(&results)
	if err != nil {
		return "", fmt.Errorf("failed to insert job record: %w", err)
	}

	if len(results) == 0 {
		return "", fmt.Errorf("no record returned after insert, job_id: %s", jobID)
	}

	log.Printf("Successfully created job record with ID: %s, Type: %s", jobID, jobType)
	return jobID, nil
}

// UpdateJobStatus updates the status, output details, and error message of an existing job record.
func UpdateJobStatus(jobID string, status string, outputDetails interface{}, errorMessage string) error {
	if client == nil {
		return fmt.Errorf("Supabase client not initialized")
	}

	updateData := make(map[string]interface{})
	updateData["status"] = status
	updateData["updated_at"] = time.Now() // Explicitly set updated_at for the update

	if outputDetails != nil {
		outputBytes, err := json.Marshal(outputDetails)
		if err != nil {
			return fmt.Errorf("failed to marshal output details: %w", err)
		}
		updateData["output_details"] = json.RawMessage(outputBytes)
	}

	if errorMessage != "" {
		updateData["error_message"] = errorMessage
	} else {
		// Ensure error_message is set to NULL if it's an empty string and was previously set,
		// or if we want to explicitly clear it.
		// However, PostgREST handles omitting fields not in updateData gracefully.
		// If you want to explicitly set it to null:
		// updateData["error_message"] = nil 
	}

	var results []VideoJobStatus // To capture the updated record if needed
	// Corrected: ExecuteTo returns (interface{}, error). We use _ to ignore the first.
	_, err := client.From(jobStatusTable).Update(updateData, "", "").Eq("job_id", jobID).ExecuteTo(&results)
	if err != nil {
		return fmt.Errorf("failed to update job record %s: %w", jobID, err)
	}

	log.Printf("Successfully updated job record %s to status: %s", jobID, status)
	return nil
}
