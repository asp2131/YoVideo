package jobs

import (
	"encoding/json"
	"fmt"
	"log"

	"videothingy/video-processor/internal/ffmpeg"
)

// GetVideoMetadataJob defines a job for retrieving video metadata.
type GetVideoMetadataJob struct {
	JobID     string // Original job ID
	InputFile string
	dbJobID   string // Stores the job_id from the database
}

// GetVideoMetadataJobPayload defines the structure for the input_payload.
type GetVideoMetadataJobPayload struct {
	JobID     string `json:"job_id"`
	InputFile string `json:"input_file"`
}

// NewGetVideoMetadataJob creates a new GetVideoMetadataJob.
func NewGetVideoMetadataJob(jobID, inputFile string) *GetVideoMetadataJob {
	return &GetVideoMetadataJob{
		JobID:     jobID,
		InputFile: inputFile,
	}
}

// ID returns the unique identifier of the job.
func (j *GetVideoMetadataJob) ID() string {
	return j.JobID
}

// Execute performs the metadata retrieval.
// It now returns the metadata (as interface{}) and an error.
func (j *GetVideoMetadataJob) Execute() (interface{}, error) {
	log.Printf("Executing GetVideoMetadataJob %s (DB ID: %s): Retrieving metadata for %s", j.JobID, j.dbJobID, j.InputFile)

	metadata, err := ffmpeg.GetFullVideoMetadata(j.InputFile)
	if err != nil {
		return nil, fmt.Errorf("failed to get video metadata for job %s (DB ID: %s): %w", j.JobID, j.dbJobID, err)
	}

	// For logging, let's marshal the metadata to a string if it's complex
	metadataJSON, _ := json.Marshal(metadata)
	log.Printf("GetVideoMetadataJob %s (DB ID: %s) completed successfully. Metadata: %s", j.JobID, j.dbJobID, string(metadataJSON))
	return metadata, nil
}

// SetDBJobID sets the database-specific job ID.
func (j *GetVideoMetadataJob) SetDBJobID(id string) {
	j.dbJobID = id
}

// GetDBJobID returns the database-specific job ID.
func (j *GetVideoMetadataJob) GetDBJobID() string {
	return j.dbJobID
}

// Type returns the type of the job.
func (j *GetVideoMetadataJob) Type() string {
	return "GET_METADATA"
}

// Payload returns the input parameters of the job for database logging.
func (j *GetVideoMetadataJob) Payload() interface{} {
	return GetVideoMetadataJobPayload{
		JobID:     j.JobID,
		InputFile: j.InputFile,
	}
}
