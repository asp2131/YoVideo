"""
Batch processing support for the video highlight pipeline.

This module provides utilities for processing multiple videos in sequence or in parallel,
with progress tracking and result aggregation.
"""
import os
import json
import time
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict, field
import logging
from tqdm import tqdm

from .core import Context
from .default_pipeline import process_video, create_default_pipeline

logger = logging.getLogger(__name__)


@dataclass
class BatchJob:
    """Represents a single job in a batch processing operation."""
    input_path: str
    output_dir: str
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the job to a dictionary."""
        return {
            'input_path': self.input_path,
            'output_dir': self.output_dir,
            'config': self.config,
            'metadata': self.metadata,
            'result': self.result,
            'error': self.error,
            'duration': self.duration
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchJob':
        """Create a BatchJob from a dictionary."""
        return cls(
            input_path=data['input_path'],
            output_dir=data['output_dir'],
            config=data.get('config', {}),
            metadata=data.get('metadata', {}),
            result=data.get('result'),
            error=data.get('error'),
            duration=data.get('duration', 0.0)
        )


@dataclass
class BatchResult:
    """Results of a batch processing operation."""
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_duration: float = 0.0
    jobs: List[BatchJob] = field(default_factory=list)
    
    def add_job(self, job: BatchJob):
        """Add a completed job to the results."""
        self.jobs.append(job)
        self.total_jobs += 1
        
        if job.error:
            self.failed_jobs += 1
        else:
            self.completed_jobs += 1
            
        self.total_duration += job.duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the batch result to a dictionary."""
        return {
            'total_jobs': self.total_jobs,
            'completed_jobs': self.completed_jobs,
            'failed_jobs': self.failed_jobs,
            'total_duration': self.total_duration,
            'jobs': [job.to_dict() for job in self.jobs]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchResult':
        """Create a BatchResult from a dictionary."""
        result = cls(
            total_jobs=data.get('total_jobs', 0),
            completed_jobs=data.get('completed_jobs', 0),
            failed_jobs=data.get('failed_jobs', 0),
            total_duration=data.get('total_duration', 0.0)
        )
        
        for job_data in data.get('jobs', []):
            result.add_job(BatchJob.from_dict(job_data))
            
        return result
    
    def save(self, output_path: Union[str, Path]):
        """Save the batch result to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, input_path: Union[str, Path]) -> 'BatchResult':
        """Load a batch result from a JSON file."""
        with open(input_path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


class BatchProcessor:
    """Processes multiple videos in batch mode."""
    
    def __init__(self, max_workers: int = 2, progress_callback: Optional[Callable] = None):
        """Initialize the batch processor.
        
        Args:
            max_workers: Maximum number of parallel workers
            progress_callback: Optional callback function for progress updates
        """
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self._stop_requested = False
    
    def stop(self):
        """Request the batch processor to stop after completing current jobs."""
        self._stop_requested = True
    
    def process_job(self, job: BatchJob) -> BatchJob:
        """Process a single job."""
        start_time = time.time()
        
        try:
            # Ensure output directory exists
            os.makedirs(job.output_dir, exist_ok=True)
            
            # Process the video
            result = process_video(
                video_path=job.input_path,
                output_dir=job.output_dir,
                config=job.config
            )
            
            job.result = result
            job.error = None
            
        except Exception as e:
            logger.error(f"Error processing {job.input_path}: {str(e)}", exc_info=True)
            job.error = str(e)
            job.result = None
        
        job.duration = time.time() - start_time
        return job
    
    def process_batch(
        self,
        input_paths: List[Union[str, Path]],
        output_dir: Union[str, Path],
        config: Optional[Dict[str, Any]] = None,
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ) -> BatchResult:
        """Process a batch of videos.
        
        Args:
            input_paths: List of input video paths
            output_dir: Base output directory (subdirectories will be created for each video)
            config: Configuration for the pipeline
            metadata_list: Optional list of metadata dictionaries (one per video)
            
        Returns:
            BatchResult with processing results
        """
        config = config or {}
        metadata_list = metadata_list or [{}] * len(input_paths)
        
        # Create batch result
        batch_result = BatchResult()
        
        # Prepare jobs
        jobs = []
        for i, (input_path, metadata) in enumerate(zip(input_paths, metadata_list)):
            input_path = str(Path(input_path).resolve())
            video_name = Path(input_path).stem
            
            job = BatchJob(
                input_path=input_path,
                output_dir=str(Path(output_dir) / video_name),
                config=config.copy(),
                metadata={
                    'index': i,
                    'video_name': video_name,
                    **metadata
                }
            )
            jobs.append(job)
        
        # Process jobs in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self.process_job, job): job 
                for job in jobs
            }
            
            # Process results as they complete
            with tqdm(total=len(jobs), desc="Processing videos") as pbar:
                for future in concurrent.futures.as_completed(future_to_job):
                    if self._stop_requested:
                        break
                        
                    job = future_to_job[future]
                    try:
                        result = future.result()
                        batch_result.add_job(result)
                        
                        # Update progress
                        pbar.update(1)
                        pbar.set_postfix({
                            'completed': batch_result.completed_jobs,
                            'failed': batch_result.failed_jobs
                        })
                        
                        # Call progress callback if provided
                        if self.progress_callback:
                            self.progress_callback(
                                total=len(jobs),
                                completed=batch_result.completed_jobs + batch_result.failed_jobs,
                                failed=batch_result.failed_jobs
                            )
                            
                    except Exception as e:
                        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
                        job.error = f"Unexpected error: {str(e)}"
                        job.duration = time.time() - job.duration  # Update duration
                        batch_result.add_job(job)
        
        return batch_result


def process_batch(
    input_paths: List[Union[str, Path]],
    output_dir: Union[str, Path],
    config: Optional[Dict[str, Any]] = None,
    max_workers: int = 2,
    progress_callback: Optional[Callable] = None
) -> BatchResult:
    """Process multiple videos in batch mode.
    
    This is a convenience function that creates a BatchProcessor and processes
    the videos in a single call.
    
    Args:
        input_paths: List of input video paths
        output_dir: Base output directory (subdirectories will be created for each video)
        config: Configuration for the pipeline
        max_workers: Maximum number of parallel workers
        progress_callback: Optional callback function for progress updates
        
    Returns:
        BatchResult with processing results
    """
    processor = BatchProcessor(
        max_workers=max_workers,
        progress_callback=progress_callback
    )
    
    return processor.process_batch(
        input_paths=input_paths,
        output_dir=output_dir,
        config=config or {}
    )


def find_videos(
    input_dir: Union[str, Path],
    extensions: Optional[List[str]] = None
) -> List[str]:
    """Find video files in a directory.
    
    Args:
        input_dir: Directory to search for videos
        extensions: List of file extensions to include (with leading .)
                  If None, uses common video extensions
                  
    Returns:
        List of paths to video files
    """
    if extensions is None:
        extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm']
    
    input_dir = Path(input_dir)
    video_paths = []
    
    for ext in extensions:
        video_paths.extend(input_dir.glob(f'**/*{ext}'))
    
    return [str(p.resolve()) for p in sorted(video_paths)]


def process_directory(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    config: Optional[Dict[str, Any]] = None,
    max_workers: int = 2,
    progress_callback: Optional[Callable] = None,
    extensions: Optional[List[str]] = None
) -> BatchResult:
    """Process all videos in a directory.
    
    Args:
        input_dir: Directory containing video files
        output_dir: Base output directory (subdirectories will be created for each video)
        config: Configuration for the pipeline
        max_workers: Maximum number of parallel workers
        progress_callback: Optional callback function for progress updates
        extensions: List of file extensions to include (with leading .)
                  
    Returns:
        BatchResult with processing results
    """
    # Find all video files
    video_paths = find_videos(input_dir, extensions)
    
    if not video_paths:
        raise ValueError(f"No video files found in {input_dir}")
    
    # Process the videos
    return process_batch(
        input_paths=video_paths,
        output_dir=output_dir,
        config=config,
        max_workers=max_workers,
        progress_callback=progress_callback
    )


# Example usage:
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process multiple videos in batch mode.')
    parser.add_argument('input', help='Input directory or file')
    parser.add_argument('output', help='Output directory')
    parser.add_argument('--workers', type=int, default=2, help='Number of worker threads')
    parser.add_argument('--config', help='Path to config file (JSON)')
    parser.add_argument('--resume', help='Resume from a previous batch result (JSON)')
    
    args = parser.parse_args()
    
    # Load config if provided
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Process the input
    input_path = Path(args.input)
    
    if input_path.is_file():
        # Process a single file
        result = process_batch(
            input_paths=[str(input_path)],
            output_dir=args.output,
            config=config,
            max_workers=1
        )
    else:
        # Process a directory
        result = process_directory(
            input_dir=input_path,
            output_dir=args.output,
            config=config,
            max_workers=args.workers
        )
    
    # Print summary
    print(f"\nBatch processing complete:")
    print(f"  Total jobs: {result.total_jobs}")
    print(f"  Completed: {result.completed_jobs}")
    print(f"  Failed: {result.failed_jobs}")
    print(f"  Total duration: {result.total_duration:.1f} seconds")
    
    # Save results
    output_file = Path(args.output) / "batch_results.json"
    result.save(output_file)
    print(f"\nResults saved to: {output_file}")
