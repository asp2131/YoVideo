package jobs

import (
	"fmt"
	"log"

	"videothingy/video-processor/internal/ffmpeg"
)

// OverlayCaptionsJob defines a job for overlaying captions onto a video.
type OverlayCaptionsJob struct {
	JobID        string // Original job ID
	InputFile    string
	CaptionsFile string
	OutputFile   string
	dbJobID      string // Stores the job_id from the database
}

// OverlayCaptionsJobPayload defines the structure for the input_payload.
type OverlayCaptionsJobPayload struct {
	JobID        string `json:"job_id"`
	InputFile    string `json:"input_file"`
	CaptionsFile string `json:"captions_file"`
	OutputFile   string `json:"output_file"`
}

// NewOverlayCaptionsJob creates a new OverlayCaptionsJob.
func NewOverlayCaptionsJob(jobID, inputFile, captionsFile, outputFile string) *OverlayCaptionsJob {
	return &OverlayCaptionsJob{
		JobID:        jobID,
		InputFile:    inputFile,
		CaptionsFile: captionsFile,
		OutputFile:   outputFile,
	}
}

// ID returns the unique identifier of the job.
func (j *OverlayCaptionsJob) ID() string {
	return j.JobID
}

// Execute performs the caption overlay.
// It now returns output details (e.g., output file path) and an error.
func (j *OverlayCaptionsJob) Execute() (interface{}, error) {
	log.Printf("Executing OverlayCaptionsJob %s (DB ID: %s): Overlaying %s on %s, output to %s",
		j.JobID, j.dbJobID, j.CaptionsFile, j.InputFile, j.OutputFile)

	err := ffmpeg.OverlayCaptions(j.InputFile, j.CaptionsFile, j.OutputFile)
	if err != nil {
		return nil, fmt.Errorf("failed to overlay captions for job %s (DB ID: %s): %w", j.JobID, j.dbJobID, err)
	}

	log.Printf("OverlayCaptionsJob %s (DB ID: %s) completed successfully. Output: %s", j.JobID, j.dbJobID, j.OutputFile)
	outputDetails := map[string]string{"output_file": j.OutputFile}
	return outputDetails, nil
}

// SetDBJobID sets the database-specific job ID.
func (j *OverlayCaptionsJob) SetDBJobID(id string) {
	j.dbJobID = id
}

// GetDBJobID returns the database-specific job ID.
func (j *OverlayCaptionsJob) GetDBJobID() string {
	return j.dbJobID
}

// Type returns the type of the job.
func (j *OverlayCaptionsJob) Type() string {
	return "OVERLAY_CAPTIONS"
}

// Payload returns the input parameters of the job for database logging.
func (j *OverlayCaptionsJob) Payload() interface{} {
	return OverlayCaptionsJobPayload{
		JobID:        j.JobID,
		InputFile:    j.InputFile,
		CaptionsFile: j.CaptionsFile,
		OutputFile:   j.OutputFile,
	}
}
