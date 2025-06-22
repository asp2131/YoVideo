#!/usr/bin/env python3
"""
Script to detect highlights in a video and create a highlight reel.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from app.editing.processors.highlight_detector import HighlightDetector
from app.editing.utils.video_utils import get_video_info, extract_segments

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def detect_highlights(
    input_path: Path,
    min_silence_len: int = 200,
    silence_thresh: int = -30,
    min_duration: float = 2.0,
    max_duration: float = 15.0
) -> dict:
    """Detect highlights in a video."""
    logger.info(f"Detecting highlights in {input_path}")
    
    # Get video info
    video_info = get_video_info(input_path)
    
    # Create detector with sensitive parameters
    detector = HighlightDetector(
        min_duration=min_duration,
        max_duration=max_duration,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=100  # Keep 100ms around cuts
    )
    
    # Detect highlights
    result = detector.process(
        input_path=input_path,
        output_path=None,  # We'll handle the output separately
        video_info=video_info
    )
    
    return result

def create_highlight_video(
    input_path: Path,
    segments: list,
    output_path: Path,
    temp_dir: Path = None
) -> bool:
    """Create a highlight video from segments."""
    if not segments:
        logger.warning("No segments to process")
        return False
    
    logger.info(f"Creating highlight video from {len(segments)} segments")
    for i, seg in enumerate(segments, 1):
        logger.info(f"  Segment {i}: {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s")
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract and concatenate segments
    try:
        result = extract_segments(
            input_path=input_path,
            segments=segments,
            output_path=output_path,
            temp_dir=temp_dir
        )
        
        if result and result.exists():
            logger.info(f"Successfully created highlight video: {result}")
            return True
        else:
            logger.error("Failed to create highlight video")
            return False
            
    except Exception as e:
        logger.error(f"Error creating highlight video: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description='Create a highlight video from a source video')
    parser.add_argument('input_video', type=str, help='Path to the input video file')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output video path (default: <input_name>_highlights.<ext>)')
    parser.add_argument('--output-json', type=str, default=None,
                        help='Output JSON path for segments (default: <input_name>_segments.json)')
    parser.add_argument('--temp-dir', type=str, default=None,
                        help='Temporary directory for processing (default: system temp)')
    
    # Detection parameters
    parser.add_argument('--min-silence-len', type=int, default=200,
                        help='Minimum silence length in ms (default: 200)')
    parser.add_argument('--silence-thresh', type=int, default=-30,
                        help='Silence threshold in dB (default: -30)')
    parser.add_argument('--min-duration', type=float, default=2.0,
                        help='Minimum highlight duration in seconds (default: 2.0)')
    parser.add_argument('--max-duration', type=float, default=15.0,
                        help='Maximum highlight duration in seconds (default: 15.0)')
    
    args = parser.parse_args()
    
    # Set up paths
    input_path = Path(args.input_video)
    if not input_path.exists():
        logger.error(f"Input video not found: {input_path}")
        return 1
    
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(f"{input_path.stem}_highlights")
    
    if args.output_json:
        json_path = Path(args.output_json)
    else:
        json_path = output_path.with_suffix('.json')
    
    # Detect highlights
    result = detect_highlights(
        input_path=input_path,
        min_silence_len=args.min_silence_len,
        silence_thresh=args.silence_thresh,
        min_duration=args.min_duration,
        max_duration=args.max_duration
    )
    
    if result.get('status') != 'success' or not result.get('segments'):
        logger.error(f"No highlights found: {result.get('message', 'Unknown error')}")
        return 1
    
    # Save segments to JSON
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved segments to {json_path}")
    
    # Create highlight video
    success = create_highlight_video(
        input_path=input_path,
        segments=result['segments'],
        output_path=output_path,
        temp_dir=Path(args.temp_dir) if args.temp_dir else None
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
