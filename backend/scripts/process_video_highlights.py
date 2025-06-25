#!/usr/bin/env python3
"""
Script to detect highlights in a video and create a highlight reel.
"""
import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import required modules
try:
    import librosa
    import matplotlib.pyplot as plt
    HAS_AUDIO_DEPS = True
except ImportError:
    HAS_AUDIO_DEPS = False
    logger = logging.getLogger(__name__)
    logger.warning("librosa or matplotlib not available. Audio feature extraction will be disabled.")

# Import local modules
from app.editing.pipeline.core import Context, Segment, HighlightPipeline
from app.editing.processors.enhanced_highlight_detector import OpusClipLevelHighlightDetector as EnhancedHighlightDetector
from app.editing.processors.scene_detector import SceneDetector
from app.editing.processors.silence_remover import SilenceRemover
from app.editing.segmenters.basic import BasicSegmenter
from app.editing.utils.video_utils import get_video_info

# Configure logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('highlight_detection.log')
    ]
)
logger = logging.getLogger(__name__)

def extract_audio(video_path: str, output_path: str) -> bool:
    """Extract audio from video using FFmpeg."""
    import subprocess
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file if it exists
        '-i', video_path,  # Input video
        '-q:a', '0',       # Best audio quality
        '-map', 'a',       # Only audio
        '-ar', '16000',    # Resample to 16kHz
        '-ac', '1',        # Convert to mono
        output_path        # Output file
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return False

def detect_highlights(
    input_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    min_duration: float = 2.0,
    max_duration: float = 15.0,
    target_duration: float = 60.0,
    min_highlight_score: float = 0.3,
    sample_rate: int = 16000,
    hop_length: int = 512,
    temp_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Detect highlights in a video with audio analysis.
    
    Args:
        input_path: Path to the input video file
        output_dir: Directory to save output files and visualizations
        min_duration: Minimum duration of a highlight segment in seconds
        max_duration: Maximum duration of a highlight segment in seconds
        target_duration: Target total duration of all highlight segments in seconds
        min_highlight_score: Minimum score for a segment to be considered a highlight (0-1)
        sample_rate: Sample rate for audio analysis
        hop_length: Hop length for audio analysis
        temp_dir: Directory for temporary files
        
    Returns:
        Dictionary containing the detected highlights and metadata
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir) if output_dir else Path.cwd() / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="highlight_"))
    else:
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Detecting highlights in {input_path}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Temporary directory: {temp_dir}")
    
    try:
        # Get video info
        video_info = get_video_info(input_path)
        duration = video_info.get('duration', 0)
        
        if duration <= 0:
            raise ValueError(f"Invalid video duration: {duration}")
            
        logger.info(f"Video duration: {duration:.2f} seconds")
        
        # Extract audio for analysis
        audio_file = temp_dir / 'audio.wav'
        logger.info(f"Extracting audio to {audio_file}")
        if not extract_audio(str(input_path), str(audio_file)):
            logger.warning("Failed to extract audio, continuing without audio analysis")
        
        # Create context for the highlight detector
        context = Context(
            video_path=str(input_path),
            duration=duration,
            output_dir=str(output_dir)
        )
        
        # Create processing pipeline
        logger.info("Creating processing pipeline")
        
        # Create processors
        silence_remover = SilenceRemover(
            silence_threshold=-30.0,
            silence_duration=0.8
        )
        
        scene_detector = SceneDetector(
            threshold=0.3,
            min_scene_len=1.5
        )
        
        segmenter = BasicSegmenter(
            min_segment_duration=min_duration,
            max_segment_duration=max_duration
        )
        
        highlight_detector = EnhancedHighlightDetector(
            min_duration=min_duration,
            max_duration=max_duration,
            target_total_duration=target_duration,
            audio_weight=0.4,
            visual_weight=0.3,
            content_weight=0.3,
            quality_threshold=min_highlight_score
        )
        
        # Create pipeline
        pipeline = HighlightPipeline([
            silence_remover,
            scene_detector,
            segmenter,
            highlight_detector
        ])
        
        # Process the video
        logger.info("Processing video through pipeline...")
        processed_context = pipeline.run(context)
        
        # Extract highlights
        highlights = getattr(processed_context, 'highlights', [])
        
        if not highlights:
            logger.warning("No highlights detected in the video")
            return {
                'status': 'success',
                'message': 'No highlights detected',
                'duration': duration,
                'highlights': [],
                'segment_count': 0,
                'highlight_count': 0
            }
        
        # Convert highlights to serializable format
        highlights_list = []
        for h in highlights:
            if isinstance(h, dict):
                highlights_list.append(h)
            else:
                # Handle Segment objects
                highlight = {
                    'start': float(h.get('start', 0)),
                    'end': float(h.get('end', 0)),
                    'duration': float(h.get('duration', 0)),
                    'score': h.get('score', 0.0),
                    'text': h.get('text', ''),
                    'speaker': h.get('speaker', ''),
                    'features': h.get('features', {})
                }
                highlights_list.append(highlight)
        
        logger.info(f"Detected {len(highlights_list)} highlights")
        
        return {
            'status': 'success',
            'message': f'Detected {len(highlights_list)} highlights',
            'duration': float(duration),
            'highlights': highlights_list,
            'segment_count': len(getattr(processed_context, 'segments', [])),
            'highlight_count': len(highlights_list),
            'audio_features': {
                'sample_rate': sample_rate,
                'hop_length': hop_length,
                'feature_count': 0  # Placeholder
            }
        }
            
    except Exception as e:
        logger.error(f"Error detecting highlights: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e),
            'duration': 0.0,
            'highlights': [],
            'segment_count': 0,
            'highlight_count': 0,
            'error': str(e)
        }

def create_highlight_video_from_segments(
    input_path: Union[str, Path],
    segments: List[Dict[str, Any]],
    output_path: Union[str, Path],
    temp_dir: Optional[Union[str, Path]] = None
) -> bool:
    """Create a highlight video from segments."""
    if not segments:
        logger.warning("No segments to process")
        return False
    
    logger.info(f"Creating highlight video from {len(segments)} segments")
    for i, seg in enumerate(segments, 1):
        logger.info(f"  Segment {i}: {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s")
    
    # Create output directory if it doesn't exist
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract and concatenate segments
    try:
        from app.editing.utils.video_utils import extract_segments
        
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

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return int(obj) if isinstance(obj, np.integer) else float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, Path):
        return str(obj)
    elif obj is None:
        return None
    raise TypeError(f"Type {type(obj)} not serializable")

def main():
    """Main function to process command line arguments and run highlight detection."""
    parser = argparse.ArgumentParser(description='Detect highlights in a video with audio analysis.')
    
    # Required arguments
    parser.add_argument('input', help='Input video file path')
    
    # Output options
    parser.add_argument('--output', default='output/highlight_reel.mp4', 
                       help='Output video file path')
    parser.add_argument('--output-dir', default='output', 
                       help='Output directory for results and intermediate files')
    
    # Duration parameters
    parser.add_argument('--min-duration', type=float, default=2.0, 
                       help='Minimum highlight duration in seconds')
    parser.add_argument('--max-duration', type=float, default=15.0, 
                       help='Maximum highlight duration in seconds')
    parser.add_argument('--target-duration', type=float, default=60.0, 
                       help='Target total duration of highlights in seconds')
    
    # Audio analysis parameters
    parser.add_argument('--min-highlight-score', type=float, default=0.3,
                       help='Minimum score for a segment to be considered a highlight (0-1)')
    parser.add_argument('--sample-rate', type=int, default=16000,
                       help='Audio sample rate for feature extraction')
    parser.add_argument('--hop-length', type=int, default=512,
                       help='Hop length for audio analysis')
    
    # Processing options
    parser.add_argument('--temp-dir', 
                       help='Temporary directory for intermediate files')
    parser.add_argument('--keep-temp', action='store_true',
                       help='Keep temporary files after processing')
    
    # Debug options
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Ensure output directory exists first
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    
    # Create handlers
    handlers = [logging.StreamHandler()]
    
    # Add file handler if output directory exists and is writable
    log_file = os.path.join(args.output_dir, 'highlight_detection.log')
    try:
        # Test if we can write to the log file
        with open(log_file, 'a'):
            pass
        handlers.append(logging.FileHandler(log_file))
    except (IOError, OSError) as e:
        print(f"Warning: Could not create log file at {log_file}: {e}")
    
    # Configure logging with the handlers
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override existing configuration
    )
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        logger.error(f"Input file {input_path} does not exist.")
        return 1
    
    try:
        # Create a subdirectory for this run's output
        run_id = f"run_{int(time.time())}"
        run_dir = Path(args.output_dir) / run_id
        os.makedirs(run_dir, exist_ok=True)
        
        logger.info(f"Starting highlight detection for {input_path}")
        logger.info(f"Output will be saved to: {output_path}")
        logger.info(f"Run directory: {run_dir}")
        
        # Set up temp directory if not provided
        temp_dir = args.temp_dir
        if not temp_dir:
            temp_dir = str(Path(tempfile.mkdtemp(prefix="highlight_")))
            logger.info(f"Using temporary directory: {temp_dir}")
        
        # Run the highlight detection pipeline with audio features
        result = detect_highlights(
            input_path=str(input_path),
            output_dir=str(run_dir),
            temp_dir=temp_dir,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            target_duration=args.target_duration,
            min_highlight_score=args.min_highlight_score,
            sample_rate=args.sample_rate,
            hop_length=args.hop_length
        )
        
        # Save results to JSON
        result_file = run_dir / 'results.json'
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2, default=json_serializer)
        
        logger.info(f"Results saved to {result_file}")
        
        # Generate highlight reel if we have highlights
        highlights = result.get('highlights', [])
        if highlights:
            logger.info(f"Generating highlight reel with {len(highlights)} segments")
            
            # Create highlight reel
            success = create_highlight_video_from_segments(
                input_path=str(input_path),
                segments=highlights,
                output_path=str(output_path),
                temp_dir=temp_dir
            )
            
            if success:
                logger.info(f"Highlight reel created at: {output_path}")
                print(f"\nSuccess! Created highlight reel at: {output_path}")
            else:
                logger.error("Failed to create highlight reel")
                print("\nFailed to create highlight reel")
        else:
            logger.warning("No highlights were detected in the video.")
            print("\nNo highlights were detected in the video.")
        
        # Clean up temp dir if not keeping it
        if not args.keep_temp and temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Removed temporary directory: {temp_dir}")
        
        return 0
            
    except Exception as e:
        logger.error(f"An error occurred during highlight detection: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
        print("Check the log file for more details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())