package jobs

import (
	"fmt"
	"log"

	"videothingy/video-processor/internal/ffmpeg"
)

// GetVideoMetadataJob defines a job for retrieving video metadata.
// It implements the worker.Job interface implicitly.
type GetVideoMetadataJob struct {
	JobID     string
	InputFile string
}

// Execute performs the metadata retrieval using the ffmpeg package.
func (gmj *GetVideoMetadataJob) Execute() error {
	log.Printf("Executing GetVideoMetadataJob %s: InputFile='%s'", gmj.JobID, gmj.InputFile)

	metadata, err := ffmpeg.GetFullVideoMetadata(gmj.InputFile)
	if err != nil {
		log.Printf("Error executing GetVideoMetadataJob %s: %v", gmj.JobID, err)
		return fmt.Errorf("GetVideoMetadataJob %s failed: %w", gmj.JobID, err)
	}

	// Log some basic info from the metadata
	formatName := "unknown"
	if format, ok := metadata["format"].(map[string]interface{}); ok {
		if fn, ok := format["format_name"].(string); ok {
			formatName = fn
		}
	}
	numStreams := 0
	if streams, ok := metadata["streams"].([]interface{}); ok {
		numStreams = len(streams)
	}

	log.Printf("Finished GetVideoMetadataJob %s: File='%s', Format='%s', Streams=%d",
		gmj.JobID, gmj.InputFile, formatName, numStreams)
	// For more detailed logging, you could marshal the whole metadata map to JSON and log it:
	// metadataJSON, _ := json.MarshalIndent(metadata, "", "  ")
	// log.Printf("Full metadata for %s:\n%s", gmj.InputFile, string(metadataJSON))

	return nil
}

// ID returns the unique identifier for GetVideoMetadataJob.
func (gmj *GetVideoMetadataJob) ID() string {
	return gmj.JobID
}
