"""
Video Highlight Processing Example

This script demonstrates how to use the video highlight pipeline to process a video,
extract highlights, and save the results.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.editing.pipeline.default_pipeline import process_video
from app.editing.pipeline.core import Context


def process_video_highlights(
    input_path: str,
    output_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    save_json: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Process a video to extract highlights.
    
    Args:
        input_path: Path to the input video file
        output_dir: Directory to save output files
        config: Optional configuration overrides
        save_json: Whether to save results to a JSON file
        verbose: Whether to print progress information
        
    Returns:
        Dictionary containing processing results
    """
    # Set default output directory if not specified
    if output_dir is None:
        output_dir = Path(input_path).parent / "output"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    if verbose:
        print(f"Processing video: {input_path}")
        print(f"Output directory: {output_dir}")
    
    try:
        # Process the video
        results = process_video(
            video_path=input_path,
            output_dir=output_dir,
            config=config or {}
        )
        
        # Save results to JSON if requested
        if save_json:
            output_path = Path(output_dir) / "highlights.json"
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            if verbose:
                print(f"\nResults saved to: {output_path}")
        
        # Print summary
        if verbose:
            print("\n=== Processing Complete ===")
            print(f"Duration: {results['duration']:.1f} seconds")
            print(f"Segments detected: {len(results['segments'])}")
            print(f"Highlights selected: {len(results['highlights'])}")
            
            # Print highlights
            print("\n=== Selected Highlights ===")
            for i, highlight in enumerate(results['highlights'], 1):
                print(f"{i}. {highlight['start']:.1f}s - {highlight['end']:.1f}s "
                      f"(score: {highlight.get('score', 0):.2f})")
                if 'text' in highlight and highlight['text']:
                    print(f"   '{highlight['text']}'")
        
        return results
        
    except Exception as e:
        print(f"Error processing video: {str(e)}", file=sys.stderr)
        raise


def main():
    """Command line interface for the video highlight processor."""
    parser = argparse.ArgumentParser(
        description='Process a video to extract highlights.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('input_path', help='Path to the input video file')
    parser.add_argument('--output-dir', help='Directory to save output files')
    parser.add_argument('--config', help='Path to JSON config file')
    parser.add_argument('--no-json', action='store_true', 
                       help='Do not save results to JSON')
    parser.add_argument('--quiet', action='store_true', 
                       help='Suppress output')
    
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
    
    # Process the video
    try:
        process_video_highlights(
            input_path=args.input_path,
            output_dir=args.output_dir,
            config=config,
            save_json=not args.no_json,
            verbose=not args.quiet
        )
        return 0
    except Exception as e:
        if not args.quiet:
            print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Example usage:
# python examples/process_video_highlights.py input.mp4 --output-dir output/
# python examples/process_video_highlights.py input.mp4 --config config.json
