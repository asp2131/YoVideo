"""
Batch Video Processing Example

This script demonstrates how to use the batch processing functionality to process
multiple videos in parallel, with progress tracking and error handling.
"""
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.editing.pipeline.batch_processor import (
    process_batch,
    process_directory,
    BatchResult
)


def print_progress(total: int, completed: int, failed: int):
    """Print progress updates."""
    print(f"\rProcessed: {completed + failed}/{total} (failed: {failed})", end="")
    if completed + failed >= total:
        print()  # Newline when done


def process_videos(
    input_paths: List[str],
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
    max_workers: int = 2,
    verbose: bool = True
) -> BatchResult:
    """
    Process multiple videos with progress tracking.
    
    Args:
        input_paths: List of input video paths
        output_dir: Output directory for results
        config: Optional pipeline configuration
        max_workers: Number of parallel workers
        verbose: Whether to print progress
        
    Returns:
        BatchResult with processing results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Processing {len(input_paths)} videos with {max_workers} workers...")
    
    # Process the videos
    result = process_batch(
        input_paths=input_paths,
        output_dir=output_dir,
        config=config or {},
        max_workers=max_workers,
        progress_callback=print_progress if verbose else None
    )
    
    return result


def process_videos_in_directory(
    input_dir: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
    max_workers: int = 2,
    extensions: Optional[List[str]] = None,
    verbose: bool = True
) -> BatchResult:
    """
    Process all videos in a directory.
    
    Args:
        input_dir: Directory containing videos
        output_dir: Output directory for results
        config: Optional pipeline configuration
        max_workers: Number of parallel workers
        extensions: List of file extensions to include
        verbose: Whether to print progress
        
    Returns:
        BatchResult with processing results
    """
    print(f"Processing videos in '{input_dir}'...")
    
    # Process the directory
    result = process_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        config=config or {},
        max_workers=max_workers,
        progress_callback=print_progress if verbose else None,
        extensions=extensions
    )
    
    return result


def save_results(result: BatchResult, output_dir: str):
    """Save batch processing results to files."""
    # Save full results
    result_path = os.path.join(output_dir, "batch_results.json")
    result.save(result_path)
    print(f"\nFull results saved to: {result_path}")
    
    # Save summary
    summary = {
        'total_jobs': result.total_jobs,
        'completed_jobs': result.completed_jobs,
        'failed_jobs': result.failed_jobs,
        'total_duration': result.total_duration,
        'avg_duration_per_job': result.total_duration / result.total_jobs if result.total_jobs > 0 else 0,
        'jobs': [
            {
                'input': job.input_path,
                'output': job.output_dir,
                'duration': job.duration,
                'error': job.error,
                'highlights_count': len(job.result.get('highlights', [])) if job.result else 0
            }
            for job in result.jobs
        ]
    }
    
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {summary_path}")
    
    # Print failed jobs
    failed = [j for j in result.jobs if j.error]
    if failed:
        print("\nFailed jobs:")
        for job in failed:
            print(f"- {job.input_path}: {job.error}")


def main():
    """Command line interface for batch video processing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process multiple videos in batch mode.')
    parser.add_argument('input', help='Input directory or file')
    parser.add_argument('output', help='Output directory')
    parser.add_argument('--workers', type=int, default=2, 
                       help='Number of parallel workers')
    parser.add_argument('--config', help='Path to config file (JSON)')
    parser.add_argument('--extensions', nargs='+', default=['.mp4', '.mov', '.avi'],
                       help='File extensions to include (with leading .)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress progress output')
    
    args = parser.parse_args()
    
    # Load config if provided
    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config file: {e}", file=sys.stderr)
            return 1
    
    # Process the input
    input_path = Path(args.input)
    
    try:
        if input_path.is_file():
            # Process a single file
            result = process_videos(
                input_paths=[str(input_path)],
                output_dir=args.output,
                config=config,
                max_workers=1,
                verbose=not args.quiet
            )
        else:
            # Process a directory
            result = process_videos_in_directory(
                input_dir=str(input_path),
                output_dir=args.output,
                config=config,
                max_workers=args.workers,
                extensions=args.extensions,
                verbose=not args.quiet
            )
        
        # Save and display results
        save_results(result, args.output)
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Example usage:
# python examples/batch_process_videos.py /path/to/videos /path/to/output --workers 4
# python examples/batch_process_videos.py single_video.mp4 /path/to/output --config config.json
