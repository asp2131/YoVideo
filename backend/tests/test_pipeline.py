""
Test script for the video highlight pipeline.

This script demonstrates how to use the default pipeline to process a video
and extract highlights.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.editing.pipeline.default_pipeline import process_video


def main():
    parser = argparse.ArgumentParser(description='Process a video and extract highlights.')
    parser.add_argument('video_path', type=str, help='Path to the input video file')
    parser.add_argument('--output-dir', type=str, default=None, 
                       help='Directory to save output files (default: same as input video)')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to JSON config file with pipeline settings')
    parser.add_argument('--save-json', action='store_true',
                       help='Save results to a JSON file')
    
    args = parser.parse_args()
    
    # Load config if provided
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Process the video
    print(f"Processing video: {args.video_path}")
    try:
        results = process_video(
            video_path=args.video_path,
            output_dir=args.output_dir,
            config=config
        )
        
        # Print summary
        print("\n=== Processing Complete ===")
        print(f"Video: {results['video_path']}")
        print(f"Duration: {results['duration']:.1f} seconds")
        print(f"Segments detected: {len(results['segments'])}")
        print(f"Highlights selected: {len(results['highlights'])}")
        
        # Print highlights
        print("\n=== Selected Highlights ===")
        for i, highlight in enumerate(results['highlights'], 1):
            print(f"{i}. {highlight['start']:.1f}s - {highlight['end']:.1f}s "
                  f"(score: {highlight['score']:.2f})")
            if 'text' in highlight and highlight['text']:
                print(f"   '{highlight['text']}'")
        
        # Save results to JSON if requested
        if args.save_json:
            output_path = Path(args.output_dir or Path(args.video_path).parent) / 'highlights.json'
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to: {output_path}")
            
    except Exception as e:
        print(f"Error processing video: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
