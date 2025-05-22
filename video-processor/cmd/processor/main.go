package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"videothingy/video-processor/internal/ffmpeg"
	"videothingy/video-processor/internal/worker"
)

// SampleJob is a concrete implementation of the worker.Job interface for testing.
type SampleJob struct {
	JobID   string
	Message string
}

// Execute performs the work for SampleJob.
func (sj *SampleJob) Execute() error {
	log.Printf("Executing SampleJob %s: %s", sj.JobID, sj.Message)
	// Simulate work
	time.Sleep(2 * time.Second)
	log.Printf("Finished SampleJob %s", sj.JobID)
	return nil
}

// ID returns the unique identifier for SampleJob.
func (sj *SampleJob) ID() string {
	return sj.JobID
}

func main() {
	log.Println("Starting Video Processor...")

	// --- Test FFmpeg GetVideoDuration ---
	videoFilePath := "/Users/akinpound/Documents/experiments/videothingy/video-processor/internal/ffmpeg/test/test.mp4" // <<<< IMPORTANT: REPLACE THIS WITH YOUR ACTUAL VIDEO FILE PATH
	log.Printf("Attempting to get duration for video: %s", videoFilePath)
	duration, err := ffmpeg.GetVideoDuration(videoFilePath)
	if err != nil {
		log.Fatalf("Error getting video duration: %v", err)
	} else {
		log.Printf("Video duration for '%s': %s", videoFilePath, duration.String())
	}
	// --- End Test FFmpeg GetVideoDuration ---

	// Initialize Dispatcher
	// Parameters: maxWorkers, jobQueueSize
	dispatcher := worker.NewDispatcher(5, 100) // 5 workers, queue size 100
	dispatcher.Run()

	// Submit some sample jobs
	for i := 1; i <= 10; i++ {
		jobID := fmt.Sprintf("sample_job_%d", i)
		job := &SampleJob{
			JobID:   jobID,
			Message: fmt.Sprintf("This is sample job number %d", i),
		}
		dispatcher.SubmitJob(job)
		time.Sleep(200 * time.Millisecond) // Stagger job submission slightly
	}

	// TODO: Initialize message queue consumer (e.g., RabbitMQ, Kafka, or polling a DB)
	// TODO: Initialize FFmpeg wrapper/service

	log.Println("Video Processor is running and jobs submitted.")

	// Graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	log.Println("Shutting down Video Processor...")
	dispatcher.Stop() // Gracefully stop the dispatcher and its workers
	log.Println("Video Processor shut down gracefully.")
}
