package worker

import (
	"log"
	"sync"

	"videothingy/video-processor/internal/db" // Added for DB interactions
)

// Job represents a unit of work to be processed.
// It includes methods for execution and identification, and now for DB interaction.
type Job interface {
	ID() string                                 // Original ID, can be different from DB Job ID
	Execute() (outputDetails interface{}, err error) // Modified to return output
	SetDBJobID(id string)                       // For storing the DB-generated job_id
	GetDBJobID() string                         // For retrieving the DB-generated job_id
	Type() string                               // e.g., "EXTRACT_CLIP", "GET_METADATA"
	Payload() interface{}                       // To get input parameters for DB logging
}

// Worker is responsible for processing jobs.
// It runs in its own goroutine and pulls jobs from a shared job queue or a dedicated channel.
type Worker struct {
	ID         int
	WorkerPool chan chan Job // A pool of channels, used to register this worker's job channel
	JobChannel chan Job      // A channel specific to this worker, to receive jobs
	Quit       chan bool     // A channel to signal the worker to stop
	Wg         *sync.WaitGroup // To signal when this worker has finished
}

// NewWorker creates a new Worker.
func NewWorker(id int, workerPool chan chan Job, wg *sync.WaitGroup) Worker {
	return Worker{
		ID:         id,
		WorkerPool: workerPool,
		JobChannel: make(chan Job),
		Quit:       make(chan bool),
		Wg:         wg,
	}
}

// Start makes the Worker listen for jobs on its JobChannel.
func (w Worker) Start() {
	w.Wg.Add(1)
	go func() {
		defer w.Wg.Done()
		for {
			// Register the current worker's JobChannel to the worker pool.
			w.WorkerPool <- w.JobChannel

			select {
			case job := <-w.JobChannel:
				dbJobID := job.GetDBJobID() // Get DB Job ID stored by Dispatcher
				log.Printf("Worker %d: Started job %s (DB ID: %s)", w.ID, job.ID(), dbJobID)

				// Update status to PROCESSING
				if dbJobID != "" {
					if err := db.UpdateJobStatus(dbJobID, "PROCESSING", nil, ""); err != nil {
						log.Printf("Worker %d: Failed to update job %s (DB ID: %s) status to PROCESSING: %v", w.ID, job.ID(), dbJobID, err)
						// Decide if we should continue or skip job if status update fails. For now, continue.
					}
				}

				output, err := job.Execute()

				if dbJobID != "" { // Update status based on execution result
					if err != nil {
						log.Printf("Worker %d: Error processing job %s (DB ID: %s): %v", w.ID, job.ID(), dbJobID, err)
						if updateErr := db.UpdateJobStatus(dbJobID, "FAILED", nil, err.Error()); updateErr != nil {
							log.Printf("Worker %d: Also failed to update job %s (DB ID: %s) status to FAILED: %v", w.ID, job.ID(), dbJobID, updateErr)
						}
					} else {
						log.Printf("Worker %d: Finished job %s (DB ID: %s) with output: %+v", w.ID, job.ID(), dbJobID, output)
						if updateErr := db.UpdateJobStatus(dbJobID, "COMPLETED", output, ""); updateErr != nil {
							log.Printf("Worker %d: Failed to update job %s (DB ID: %s) status to COMPLETED: %v", w.ID, job.ID(), dbJobID, updateErr)
						}
					}
				} else if err != nil { // Case where dbJobID was not set, but job failed
					log.Printf("Worker %d: Error processing job %s (DB ID not set): %v", w.ID, job.ID(), err)
				} else { // Case where dbJobID was not set, and job succeeded
					log.Printf("Worker %d: Finished job %s (DB ID not set) with output: %+v", w.ID, job.ID(), output)
				}

			case <-w.Quit:
				log.Printf("Worker %d: Stopping", w.ID)
				return
			}
		}
	}()
}

// Stop signals the worker to stop processing new jobs.
func (w Worker) Stop() {
	go func() {
		w.Quit <- true
	}()
}

// Dispatcher manages a pool of workers and dispatches jobs to them.
type Dispatcher struct {
	MaxWorkers int
	WorkerPool chan chan Job // A pool of worker job channels
	JobQueue   chan Job      // A buffered channel for incoming jobs
	Workers    []Worker
	Wg         sync.WaitGroup // To wait for all workers to finish
	Quit       chan bool      // To signal the dispatcher and workers to stop
}

// NewDispatcher creates a new Dispatcher.
func NewDispatcher(maxWorkers int, jobQueueSize int) *Dispatcher {
	jobQueue := make(chan Job, jobQueueSize)
	workerPool := make(chan chan Job, maxWorkers)
	return &Dispatcher{
		MaxWorkers: maxWorkers,
		WorkerPool: workerPool,
		JobQueue:   jobQueue,
		Workers:    make([]Worker, 0, maxWorkers),
		Quit:       make(chan bool),
	}
}

// Run starts the dispatcher and its workers.
func (d *Dispatcher) Run() {
	log.Printf("Dispatcher starting with %d workers...", d.MaxWorkers)
	for i := 1; i <= d.MaxWorkers; i++ {
		worker := NewWorker(i, d.WorkerPool, &d.Wg)
		d.Workers = append(d.Workers, worker)
		worker.Start()
	}

	go d.dispatch()
	log.Println("Dispatcher is running.")
}

// dispatch listens to the JobQueue and sends jobs to available workers.
func (d *Dispatcher) dispatch() {
	for {
		select {
		case job := <-d.JobQueue:
			// A job request has been received. Try to obtain a worker job channel.
			go func(job Job) {
				// Wait for a worker to become available.
				jobChannel := <-d.WorkerPool
				// Dispatch the job to the worker's job channel.
				jobChannel <- job
			}(job)
		case <-d.Quit: // If dispatcher is told to quit
			log.Println("Dispatcher: Stopping dispatch loop")
			return
		}
	}
}

// SubmitJob sends a job to the job queue.
func (d *Dispatcher) SubmitJob(job Job) {
	// Create a record in the database for this job
	dbJobID, err := db.CreateJobRecord(job.Type(), job.Payload())
	if err != nil {
		log.Printf("Dispatcher: Failed to create DB record for job %s (Type: %s): %v. Job will not be submitted.", job.ID(), job.Type(), err)
		// Depending on policy, we might want to still queue the job, or have a fallback.
		// For now, if DB record creation fails, we don't queue it.
		return
	}
	job.SetDBJobID(dbJobID) // Store the DB-generated job_id in the job itself
	log.Printf("Dispatcher: Job %s (Type: %s) recorded in DB with ID: %s", job.ID(), job.Type(), dbJobID)

	select {
	case d.JobQueue <- job:
		log.Printf("Dispatcher: Job %s (DB ID: %s) submitted to queue.", job.ID(), dbJobID)
	default:
		log.Printf("Dispatcher: Job queue full. Job %s (DB ID: %s) could not be submitted.", job.ID(), dbJobID)
		// If the queue is full, the job was recorded in DB as PENDING but won't be processed immediately.
		// This state needs to be managed (e.g., a separate process could pick up PENDING jobs later, or status needs update).
		// For now, we'll log it. A more robust system might update status to QUEUE_FAILED or similar.
		// Or, try to re-submit later.
		if err := db.UpdateJobStatus(dbJobID, "QUEUE_FAILED", nil, "Job queue was full"); err != nil {
			log.Printf("Dispatcher: Also failed to update status for job %s (DB ID: %s) to QUEUE_FAILED: %v", job.ID(), dbJobID, err)
		}
	}
}

// Stop gracefully shuts down the dispatcher and all its workers.
func (d *Dispatcher) Stop() {
	log.Println("Dispatcher: Initiating shutdown...")
	// Signal the dispatch loop to stop.
	d.Quit <- true

	// Signal all workers to stop.
	for _, worker := range d.Workers {
		worker.Stop()
	}

	// Wait for all workers to complete their current jobs and exit.
	d.Wg.Wait()
	log.Println("Dispatcher: All workers have stopped.")
	close(d.JobQueue)
	close(d.WorkerPool)
	log.Println("Dispatcher: Shutdown complete.")
}
