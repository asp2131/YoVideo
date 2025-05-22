package jobs

import (
	"fmt"
	"log"
	"time"

	"videothingy/video-processor/internal/ffmpeg"
)

// ExtractClipJob defines a job for extracting a clip from a video.
type ExtractClipJob struct {
	JobID        string // Original job ID, can be different from DB job ID
	InputFile    string
	OutputFile   string
	StartTimeStr string
	ClipDurationStr string
	StartTime    time.Duration // Corrected type
	ClipDuration time.Duration // Corrected type
	dbJobID      string        // Stores the job_id from the database
}

// ExtractClipJobPayload defines the structure for the input_payload in the database.
// This ensures durations are stored as human-readable strings.
type ExtractClipJobPayload struct {
	JobID        string `json:"job_id"`
	InputFile    string `json:"input_file"`
	OutputFile   string `json:"output_file"`
	StartTime    string `json:"start_time"`
	ClipDuration string `json:"clip_duration"`
	// dbJobID is internal and not part of the payload sent to the DB initially
}

// NewExtractClipJob creates a new ExtractClipJob.
// It now parses startTimeStr and clipDurationStr and returns an error if parsing fails.
func NewExtractClipJob(jobID, inputFile, outputFile, startTimeStr, clipDurationStr string) (*ExtractClipJob, error) {
	startTime, err := time.ParseDuration(startTimeStr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse start time '%s': %w", startTimeStr, err)
	}
	clipDuration, err := time.ParseDuration(clipDurationStr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse clip duration '%s': %w", clipDurationStr, err)
	}

	return &ExtractClipJob{
		JobID:           jobID,
		InputFile:       inputFile,
		OutputFile:      outputFile,
		StartTimeStr:    startTimeStr,
		ClipDurationStr: clipDurationStr,
		StartTime:       startTime,    // Parsed duration
		ClipDuration:    clipDuration, // Parsed duration
	}, nil
}

// ID returns the unique identifier of the job.
func (j *ExtractClipJob) ID() string {
	return j.JobID
}

// Execute performs the clip extraction.
// It now returns output details (e.g., output file path) and an error.
func (j *ExtractClipJob) Execute() (interface{}, error) {
	log.Printf("Executing ExtractClipJob %s (DB ID: %s): Extracting from %s to %s, StartTime: %s, ClipDuration: %s",
		j.JobID, j.dbJobID, j.InputFile, j.OutputFile, j.StartTimeStr, j.ClipDurationStr)

	err := ffmpeg.ExtractClip(j.InputFile, j.OutputFile, j.StartTime, j.ClipDuration)
	if err != nil {
		return nil, fmt.Errorf("failed to extract clip for job %s (DB ID: %s): %w", j.JobID, j.dbJobID, err)
	}

	log.Printf("ExtractClipJob %s (DB ID: %s) completed successfully. Output: %s", j.JobID, j.dbJobID, j.OutputFile)
	outputDetails := map[string]string{"output_file": j.OutputFile}
	return outputDetails, nil
}

// SetDBJobID sets the database-specific job ID.
func (j *ExtractClipJob) SetDBJobID(id string) {
	j.dbJobID = id
}

// GetDBJobID returns the database-specific job ID.
func (j *ExtractClipJob) GetDBJobID() string {
	return j.dbJobID
}

// Type returns the type of the job.
func (j *ExtractClipJob) Type() string {
	return "EXTRACT_CLIP"
}

// Payload returns the input parameters of the job for database logging.
// It returns a specific struct to control JSON marshalling, especially for durations.
func (j *ExtractClipJob) Payload() interface{} {
	return ExtractClipJobPayload{
		JobID:        j.JobID, // This JobID is the one passed to NewExtractClipJob
		InputFile:    j.InputFile,
		OutputFile:   j.OutputFile,
		StartTime:    j.StartTimeStr,    // Convert duration to string for payload
		ClipDuration: j.ClipDurationStr, // Convert duration to string for payload
	}
}
