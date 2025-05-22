package jobs

import (
	"fmt"
	"log"
	"time"

	"videothingy/video-processor/internal/ffmpeg"
)

// ExtractClipJob defines a job for extracting a video clip.
// It implements the worker.Job interface implicitly.
type ExtractClipJob struct {
	JobID        string
	InputFile    string
	OutputFile   string
	StartTime    time.Duration
	ClipDuration time.Duration
}

// Execute performs the clip extraction using the ffmpeg package.
func (ecj *ExtractClipJob) Execute() error {
	log.Printf("Executing ExtractClipJob %s: Input='%s', Output='%s', StartTime='%s', Duration='%s'",
		ecj.JobID, ecj.InputFile, ecj.OutputFile, ecj.StartTime, ecj.ClipDuration)

	err := ffmpeg.ExtractClip(ecj.InputFile, ecj.OutputFile, ecj.StartTime, ecj.ClipDuration)
	if err != nil {
		log.Printf("Error executing ExtractClipJob %s: %v", ecj.JobID, err)
		return fmt.Errorf("ExtractClipJob %s failed: %w", ecj.JobID, err)
	}

	log.Printf("Finished ExtractClipJob %s: Successfully created clip '%s'", ecj.JobID, ecj.OutputFile)
	return nil
}

// ID returns the unique identifier for ExtractClipJob.
func (ecj *ExtractClipJob) ID() string {
	return ecj.JobID
}
