#!/usr/bin/env python3
"""
Script to create a highlight video from a source video and segments JSON.
"""
import argparse
import json
import logging
from pathlib import Path

from app.editing.utils.video_utils import extract_segments

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_segments(segments_path: Path) -> list:
    """Load segments from a JSON file."""
    try:
        with open(segments_path, 'r') as f:
            segments = json.load(f)
        if not isinstance(segments, list):
            logger.error("Segments file should contain a list of segments")
            return []
        return segments
    except Exception as e:
        logger.error(f"Error loading segments from {segments_path}: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Create a highlight video from segments')
    parser.add_argument('input_video', type=str, help='Path to the input video file')
    parser.add_argument('segments_json', type=str, help='Path to the segments JSON file')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output video path (default: <input_name>_highlights.<ext>)')
    parser.add_argument('--temp-dir', type=str, default=None,
                        help='Temporary directory for processing (default: system temp)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_video)
    if not input_path.exists():
        logger.error(f"Input video not found: {input_path}")
        return 1
    
    segments_path = Path(args.segments_json)
    if not segments_path.exists():
        logger.error(f"Segments file not found: {segments_path}")
        return 1
    
    # Set default output path if not provided
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(f"{input_path.stem}_highlights")
    
    # Set temp directory
    temp_dir = Path(args.temp_dir) if args.temp_dir else None
    
    # Load segments
    segments = load_segments(segments_path)
    if not segments:
        logger.error("No valid segments found")
        return 1
    
    logger.info(f"Found {len(segments)} segments to extract")
    for i, seg in enumerate(segments, 1):
        logger.info(f"Segment {i}: {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s")
    
    # Extract and concatenate segments
    logger.info(f"Creating highlight video: {output_path}")
    try:
        result = extract_segments(
            input_path=input_path,
            segments=segments,
            output_path=output_path,
            temp_dir=temp_dir
        )
        
        if result and result.exists():
            logger.info(f"Successfully created highlight video: {result}")
            return 0
        else:
            logger.error("Failed to create highlight video")
            return 1
            
    except Exception as e:
        logger.error(f"Error creating highlight video: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
