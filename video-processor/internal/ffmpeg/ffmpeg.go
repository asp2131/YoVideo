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

// GetFullVideoMetadata retrieves comprehensive format and stream metadata for a video file.
func GetFullVideoMetadata(filePath string) (map[string]interface{}, error) {
	cmd := exec.Command("ffprobe",
		"-v", "quiet",
		"-print_format", "json",
		"-show_format",
		"-show_streams",
		filePath,
	)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return nil, fmt.Errorf("ffprobe -show_format -show_streams failed: %v\nStderr: %s", err, stderr.String())
	}

	var metadata map[string]interface{}
	if err := json.Unmarshal(stdout.Bytes(), &metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal ffprobe JSON output: %v\nStdout: %s", err, stdout.String())
	}

	log.Printf("Successfully retrieved full metadata for '%s'", filePath)
	return metadata, nil
}

// OverlayCaptions overlays the captions from captionsFile (e.g., SRT) onto the inputFile video,
// saving the result to outputFile.
func OverlayCaptions(inputFile, captionsFile, outputFile string) error {
	// ffmpeg -i inputFile -vf subtitles=captionsFile outputFile
	// Ensure the captionsFile path is properly escaped for FFmpeg if it contains special characters.
	// For simplicity, we assume paths are straightforward here.
	// FFmpeg might need absolute paths for subtitle files, or paths relative to its CWD.
	// Using absolute paths is generally safer.

	// Construct the filter string. Note: paths in subtitles filter might need careful handling
	// depending on OS and FFmpeg version, especially with special characters or spaces.
	// For FFmpeg on Unix-like systems, direct path usually works.
	// On Windows, paths might need escaping (e.g., C\:\\path\\to\\file.srt).
	// Let's assume Unix-like paths for now.
	subtitlesFilter := fmt.Sprintf("subtitles='%s'", captionsFile)

	cmd := exec.Command("ffmpeg",
		"-y", // Overwrite output file if it exists
		"-i", inputFile,
		"-vf", subtitlesFilter,
		outputFile,
	)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("ffmpeg -vf subtitles failed: %v\nStderr: %s", err, stderr.String())
	}

	log.Printf("Successfully overlaid captions from '%s' onto '%s', output to '%s'", captionsFile, inputFile, outputFile)
	return nil
}

// Additional FFmpeg wrapper functions can be added here as needed.
