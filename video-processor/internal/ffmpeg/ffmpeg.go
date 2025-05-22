package ffmpeg

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"strconv"
	"time"
)

// FFProbeOutput defines the structure for ffprobe JSON output relevant to duration.
// We only care about the format.duration field for this example.
type FFProbeOutput struct {
	Format struct {
		Duration string `json:"duration"`
	} `json:"format"`
}

// GetVideoDuration uses ffprobe to get the duration of a video file.
// It returns the duration as a time.Duration and an error if any occurs.
func GetVideoDuration(filePath string) (time.Duration, error) {
	// ffprobe -v quiet -print_format json -show_format -show_streams <input_file>
	cmd := exec.Command("ffprobe",
		"-v", "quiet",
		"-print_format", "json",
		"-show_format",
		filePath,
	)

	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return 0, fmt.Errorf("ffprobe failed: %v\nStderr: %s", err, stderr.String())
	}

	var ffprobeOutput FFProbeOutput
	if err := json.Unmarshal(out.Bytes(), &ffprobeOutput); err != nil {
		return 0, fmt.Errorf("error unmarshalling ffprobe output: %v\nOutput: %s", err, out.String())
	}

	if ffprobeOutput.Format.Duration == "" {
		return 0, fmt.Errorf("could not retrieve duration from ffprobe output\nOutput: %s", out.String())
	}

	durationFloat, err := strconv.ParseFloat(ffprobeOutput.Format.Duration, 64)
	if err != nil {
		return 0, fmt.Errorf("error parsing duration string '%s': %v", ffprobeOutput.Format.Duration, err)
	}

	return time.Duration(durationFloat * float64(time.Second)), nil
}

// ExtractClip creates a video clip from the inputFile, starting at startTime and lasting for clipDuration.
// The output is saved to outputFile.
// It uses '-c copy' for fast, lossless clipping where possible.
func ExtractClip(inputFile, outputFile string, startTime, clipDuration time.Duration) error {
	// Format startTime and clipDuration for FFmpeg (e.g., in seconds)
	startSeconds := fmt.Sprintf("%.3f", startTime.Seconds())
	durationSeconds := fmt.Sprintf("%.3f", clipDuration.Seconds())

	// ffmpeg -y -i <inputFile> -ss <startTime> -t <duration> <outputFile>
	cmd := exec.Command("ffmpeg",
		"-y", // Overwrite output file if it exists
		"-i", inputFile,
		"-ss", startSeconds,
		"-t", durationSeconds,
		// "-c", "copy", // Removed for frame accuracy; allows re-encoding
		outputFile,
	)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("ffmpeg -ss failed: %v\nStderr: %s", err, stderr.String())
	}

	log.Printf("Successfully extracted clip from '%s' to '%s' (start: %s, duration: %s)", inputFile, outputFile, startTime, clipDuration)
	return nil
}

// TODO: Add more FFmpeg wrapper functions here, e.g.:
// - OverlayCaptions(inputFile, outputFile, captionsFile string) error
// - GetVideoMetadata(filePath string) (map[string]interface{}, error) // More comprehensive metadata
