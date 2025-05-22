package worker

import (
	"log"
	"sync"
)

// Job represents a unit of work to be executed.
// It could carry data specific to the task, e.g., video ID, processing parameters.

type Job interface {
	Execute() error // The method that performs the actual work
	ID() string       // A unique identifier for the job
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
				log.Printf("Worker %d: Started job %s", w.ID, job.ID())
				if err := job.Execute(); err != nil {
					log.Printf("Worker %d: Error processing job %s: %v", w.ID, job.ID(), err)
					// TODO: Implement error handling (e.g., retry, dead-letter queue)
				} else {
					log.Printf("Worker %d: Finished job %s", w.ID, job.ID())
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

// SubmitJob adds a job to the job queue.
func (d *Dispatcher) SubmitJob(job Job) {
	// Non-blocking submit, or handle queue full scenario
	select {
	case d.JobQueue <- job:
		log.Printf("Dispatcher: Job %s submitted to queue.", job.ID())
	default:
		log.Printf("Dispatcher: Job queue full. Job %s could not be submitted.", job.ID())
		// TODO: Handle queue full scenario (e.g., return error, retry, etc.)
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
