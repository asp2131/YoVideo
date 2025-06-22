#!/usr/bin/env python3
"""
Test script for the HighlightDetector processor.

Usage:
    python -m scripts.test_highlight_detector <input_video> [--output-dir OUTPUT_DIR]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.editing.processors.highlight_detector import HighlightDetector
from app.editing.core.processor import VideoEditingError
from app.editing.utils.video_utils import get_video_info

def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('highlight_detector.log')
        ]
    )

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test HighlightDetector')
    parser.add_argument('input_video', type=str, help='Path to input video file')
    parser.add_argument('--output-dir', type=str, default='output',
                       help='Output directory for results (default: output/)')
    parser.add_argument('--min-duration', type=float, default=5.0,
                       help='Minimum highlight duration (default: 5.0)')
    parser.add_argument('--max-duration', type=float, default=30.0,
                       help='Maximum highlight duration (default: 30.0)')
    parser.add_argument('--min-silence-len', type=float, default=0.5,
                       help='Minimum silence length (default: 0.5)')
    parser.add_argument('--silence-thresh', type=float, default=0.01,
                       help='Silence threshold (default: 0.01)')
    parser.add_argument('--keep-silence', action='store_true',
                       help='Keep silence segments (default: False)')
    return parser.parse_args()

def format_timestamp(timestamp):
    """Format timestamp as HH:MM:SS."""
    hours = int(timestamp // 3600)
    minutes = int((timestamp % 3600) // 60)
    seconds = int(timestamp % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def main():
    """Main function to test the HighlightDetector."""
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Get video info
        video_path = Path(args.input_video)
        if not video_path.exists():
            logger.error(f"Input video not found: {video_path}")
            return 1
            
        video_info = get_video_info(video_path)
        if not video_info:
            logger.error("Could not get video info")
            return 1
            
        logger.info(f"Video info: {json.dumps(video_info, indent=2)}")
        
        # Initialize detector
        detector = HighlightDetector(
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            min_silence_len=args.min_silence_len,
            silence_thresh=args.silence_thresh,
            keep_silence=args.keep_silence
        )
        
        # Process video
        logger.info("Processing video...")
        result = detector.process(video_path, video_info)
        
        if result["status"] != "success":
            logger.error(f"Error processing video: {result.get('message', 'Unknown error')}")
            return 1
            
        # Save results
        output_file = output_dir / f"{video_path.stem}_highlights.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Print summary
        total_duration = result["total_duration"]
        segments = result["segments"]
        total_highlight = sum(seg["end"] - seg["start"] for seg in segments)
        
        logger.info("\n=== Highlight Detection Results ===")
        logger.info(f"Input video: {video_path}")
        logger.info(f"Duration: {format_timestamp(total_duration)}")
        logger.info(f"Detected {len(segments)} highlight segments")
        logger.info(f"Total highlight duration: {format_timestamp(total_highlight)}")
        logger.info(f"Reduction: {((1 - total_highlight/total_duration)*100):.1f}%")
        
        logger.info("\n=== Segments ===")
        for i, seg in enumerate(segments, 1):
            logger.info(f"{i:2d}. {format_timestamp(seg['start'])} - {format_timestamp(seg['end'])} "
                      f"({seg['end']-seg['start']:.1f}s)")
        
        logger.info(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
