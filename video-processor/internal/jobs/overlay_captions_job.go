package jobs

import (
	"fmt"
	"log"

	"videothingy/video-processor/internal/ffmpeg"
)

// OverlayCaptionsJob defines a job for overlaying captions onto a video.
// It implements the worker.Job interface implicitly.
type OverlayCaptionsJob struct {
	JobID        string
	InputFile    string
	CaptionsFile string // Path to the SRT file
	OutputFile   string
}

// Execute performs the caption overlay using the ffmpeg package.
func (ocj *OverlayCaptionsJob) Execute() error {
	log.Printf("Executing OverlayCaptionsJob %s: Input='%s', Captions='%s', Output='%s'",
		ocj.JobID, ocj.InputFile, ocj.CaptionsFile, ocj.OutputFile)

	err := ffmpeg.OverlayCaptions(ocj.InputFile, ocj.CaptionsFile, ocj.OutputFile)
	if err != nil {
		log.Printf("Error executing OverlayCaptionsJob %s: %v", ocj.JobID, err)
		return fmt.Errorf("OverlayCaptionsJob %s failed: %w", ocj.JobID, err)
	}

	log.Printf("Finished OverlayCaptionsJob %s: Successfully overlaid captions on '%s' to create '%s'",
		ocj.JobID, ocj.InputFile, ocj.OutputFile)
	return nil
}

// ID returns the unique identifier for OverlayCaptionsJob.
func (ocj *OverlayCaptionsJob) ID() string {
	return ocj.JobID
}
