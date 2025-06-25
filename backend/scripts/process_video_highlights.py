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
from app.editing.pipeline.core import Context, Segment
from app.editing.processors.enhanced_highlight_detector import OpusClipLevelHighlightDetector as EnhancedHighlightDetector
from app.editing.segmenters.intelligent_segmenter import IntelligentSegmenter
from app.editing.utils.ffmpeg_utils import run_ffmpeg
from app.editing.utils.video_utils import extract_audio, get_video_info

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

from app.editing.segmenters.intelligent_segmenter import IntelligentSegmenter
from app.editing.utils.ffmpeg_utils import run_ffmpeg
import tempfile
import os
import numpy as np
import librosa
import json
from typing import List, Dict, Any, Tuple

def extract_audio_features(audio_path: str, sample_rate: int = 16000, hop_length: int = 512) -> Dict[str, np.ndarray]:
    """Extract audio features using librosa."""
    try:
        # Load audio file
        y, sr = librosa.load(audio_path, sr=sample_rate)
        
        # Extract features
        features = {}
        
        # Time-domain features
        features['rms_energy'] = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        features['zcr'] = librosa.feature.zero_crossing_rate(y, hop_length=hop_length)[0]
        
        # Frequency-domain features
        S = np.abs(librosa.stft(y, hop_length=hop_length))
        features['spectral_centroid'] = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
        features['spectral_bandwidth'] = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
        features['spectral_rolloff'] = librosa.feature.spectral_rolloff(S=S, sr=sr)[0]
        
        # MFCCs
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)
        for i, mf in enumerate(mfcc):
            features[f'mfcc_{i}'] = mf
        
        # Calculate frame times
        times = librosa.times_like(features['rms_energy'], sr=sr, hop_length=hop_length)
        features['times'] = times
        
        return features
    except Exception as e:
        logger.error(f"Error extracting audio features: {e}")
        return {}

def extract_audio(video_path: str, output_path: str) -> bool:
    """Extract audio from video using FFmpeg."""
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
        run_ffmpeg(cmd)
        return True
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return False

def map_features_to_segments(
    segments: List[Dict[str, Any]], 
    audio_features: Dict[str, np.ndarray],
    sample_rate: int = 16000,
    hop_length: int = 512
) -> List[Dict[str, Any]]:
    """
    Map audio features to segments.
    
    Args:
        segments: List of segment dictionaries with 'start' and 'end' times
        audio_features: Dictionary of audio features with 'times' array
        sample_rate: Audio sample rate
        hop_length: Hop length used in feature extraction
        
    Returns:
        List of segments with audio features added
    """
    if not audio_features or 'times' not in audio_features:
        logger.warning("No audio features or timestamps found")
        return segments
    
    times = audio_features['times']
    
    for segment in segments:
        start_time = segment['start']
        end_time = segment['end']
        
        # Find indices of frames within this segment
        frame_mask = (times >= start_time) & (times <= end_time)
        
        # Skip if no frames in this segment
        if not np.any(frame_mask):
            logger.warning(f"No audio frames found in segment {start_time:.2f}-{end_time:.2f}")
            continue
        
        # Calculate mean and max values for each feature in this segment
        segment_features = {}
        for feature_name, feature_values in audio_features.items():
            if feature_name == 'times':
                continue
                
            segment_values = feature_values[frame_mask]
            if len(segment_values) == 0:
                continue
                
            # Calculate statistics for this feature in this segment
            segment_features[f'{feature_name}_mean'] = float(np.mean(segment_values))
            segment_features[f'{feature_name}_max'] = float(np.max(segment_values))
            
            # For energy, also calculate ratio to overall mean
            if 'rms_energy' in feature_name:
                overall_mean = np.mean(feature_values) if len(feature_values) > 0 else 1.0
                segment_features['energy_ratio'] = float(np.mean(segment_values) / (overall_mean + 1e-10))
        
        # Add features to segment
        segment.update(segment_features)
    
    return segments

def plot_audio_features(audio_features: Dict[str, np.ndarray], output_path: str):
    """Plot audio features for visualization."""
    if not audio_features or 'times' not in audio_features:
        return
    
    times = audio_features['times']
    
    # Create subplots
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    
    # Plot RMS Energy
    if 'rms_energy' in audio_features:
        axes[0].plot(times, audio_features['rms_energy'], label='RMS Energy')
        axes[0].set_ylabel('Amplitude')
        axes[0].set_title('RMS Energy')
        axes[0].grid(True)
    
    # Plot Spectral Centroid
    if 'spectral_centroid' in audio_features:
        axes[1].plot(times, audio_features['spectral_centroid'], label='Spectral Centroid', color='g')
        axes[1].set_ylabel('Hz')
        axes[1].set_title('Spectral Centroid (Brightness)')
        axes[1].grid(True)
    
    # Plot Zero Crossing Rate
    if 'zcr' in audio_features:
        axes[2].plot(times, audio_features['zcr'], label='ZCR', color='r')
        axes[2].set_ylabel('Rate')
        axes[2].set_title('Zero Crossing Rate')
        axes[2].grid(True)
    
    # Plot MFCCs (first 5 coefficients)
    mfccs = [f'mfcc_{i}' for i in range(5) if f'mfcc_{i}' in audio_features]
    if mfccs:
        for i, mfcc in enumerate(mfccs[:5]):  # Only plot first 5 MFCCs for clarity
            axes[3].plot(times, audio_features[mfcc], label=f'MFCC {i}')
        axes[3].set_xlabel('Time (s)')
        axes[3].set_ylabel('Coefficient')
        axes[3].set_title('MFCCs')
        axes[3].legend()
        axes[3].grid(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved audio feature visualization to {output_path}")

async def _process_video_async(
    pipeline: Any,
    input_path: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Helper function to run the async video processing."""
    return await pipeline.process_video_to_opus_clip_quality(
        video_path=input_path,
        output_dir=output_dir
    )

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
        extract_audio(
            str(input_path),
            str(audio_file)
        )
        
        # Load audio for feature extraction
        y, sr = librosa.load(str(audio_file), sr=sample_rate)
        
        # Extract audio features
        logger.info("Extracting audio features")
        features = {}
        
        # Extract various audio features
        features['rms'] = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        features['spectral_centroid'] = librosa.feature.spectral_centroid(
            y=y, sr=sr, hop_length=hop_length)[0]
        features['zcr'] = librosa.feature.zero_crossing_rate(
            y, hop_length=hop_length)[0]
        features['spectral_bandwidth'] = librosa.feature.spectral_bandwidth(
            y=y, sr=sr, hop_length=hop_length)[0]
        features['spectral_rolloff'] = librosa.feature.spectral_rolloff(
            y=y, sr=sr, hop_length=hop_length)[0]
        
        # Extract MFCCs
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)
        for i, mfcc in enumerate(mfccs):
            features[f'mfcc_{i}'] = mfcc
        
        # Calculate time points for each feature frame
        times = librosa.times_like(features['rms'], sr=sr, hop_length=hop_length)
        
        # Create context for the highlight detector
        context = Context(
            video_path=str(input_path)
        )
        context.temp_dir = str(temp_dir)
        context.sample_rate = sample_rate
        context.hop_length = hop_length
        context.feature_times = times
        context.audio_features = features
        
        # Create segments using OpusClipLevelPipeline
        logger.info("Creating segments using OpusClipLevelPipeline")
        
        # Create a configuration object
        from app.editing.segmenters.intelligent_segmenter import OpusClipConfig
        config = OpusClipConfig(
            min_segment_duration=min_duration,
            max_segment_duration=max_duration,
            target_total_duration=target_duration,
            min_highlight_duration=min_duration,
            max_highlight_duration=max_duration,
            quality_threshold=0.3
        )
        
        # Initialize the pipeline with the config
        pipeline = IntelligentSegmenter(config=config)
        
        # Process the video to get highlights using asyncio.run()
        logger.info("Processing video to extract highlights...")
        import asyncio
        results = asyncio.run(_process_video_async(
            pipeline=pipeline,
            input_path=str(input_path),
            output_dir=str(output_dir) if output_dir else None
        ))
        
        # Convert the results to segments
        context.segments = [
            Segment(
                start=seg['start'],
                end=seg['end'],
                text=seg.get('text', ''),
                speaker=seg.get('speaker', ''),
                scene_change=seg.get('scene_change', False),
                silent_ratio=seg.get('silence_ratio', 0.0),
                word_count=len(seg.get('text', '').split()) if seg.get('text') else 0,
                audio_peaks=seg.get('audio_peaks', 0.0),
                visual_motion=seg.get('visual_motion', 0.0),
                sentiment=seg.get('sentiment', 0.0)
            )
            for seg in results.get('segments', [])
        ]
        
        logger.info(f"Created {len(context.segments)} segments")
        
        # Initialize the highlight detector with enhanced parameters
        detector = EnhancedHighlightDetector(
            min_duration=min_duration,
            max_duration=max_duration,
            target_total_duration=target_duration,
            audio_weight=0.6,  # Higher weight for audio features
            visual_weight=0.2,
            content_weight=0.2,
            scene_change_bonus=0.1,
            silence_penalty=0.2,
            face_detection_enabled=False,  # Disable face detection for now
            motion_analysis_enabled=False  # Disable motion analysis for now
        )
        
        # Process the video to detect highlights
        logger.info("Detecting highlights...")
        context = detector.process(context)
        
        if not context.highlights:
            logger.warning("No highlights detected in the video")
            return {
                'status': 'success',
                'message': 'No highlights detected',
                'duration': duration,
                'highlights': [],
                'segment_count': 0,
                'highlight_count': 0
            }
        
        # Convert highlights to dict for JSON serialization
        highlights = []
        for h in context.highlights:
            # Handle both Segment objects and dictionaries
            if hasattr(h, 'start'):  # It's a Segment object
                highlight = {
                    'start': float(h.start),
                    'end': float(h.end),
                    'duration': float(h.end - h.start),
                    'score': getattr(h, 'score', 0.0),
                    'text': getattr(h, 'text', ''),
                    'speaker': getattr(h, 'speaker', None),
                    'scene_change': getattr(h, 'scene_change', False),
                    'sentiment': getattr(h, 'sentiment', 0.0)
                }
            else:  # It's already a dictionary
                highlight = {
                    'start': float(h.get('start', 0)),
                    'end': float(h.get('end', 0)),
                    'duration': float(h.get('end', 0) - h.get('start', 0)),
                    'score': h.get('score', 0.0),
                    'text': h.get('text', ''),
                    'speaker': h.get('speaker'),
                    'scene_change': h.get('scene_change', False),
                    'sentiment': h.get('sentiment', 0.0)
                }
            highlights.append(highlight)
        
        logger.info(f"Detected {len(highlights)} highlights")
        
        # Visualize audio features if matplotlib is available
        if 'matplotlib' in sys.modules and HAS_AUDIO_DEPS:
            try:
                plt.figure(figsize=(12, 8))
                
                # Plot RMS energy
                plt.subplot(3, 1, 1)
                plt.plot(times, features['rms'], label='RMS Energy')
                plt.title('Audio Features')
                plt.ylabel('Amplitude')
                
                # Plot spectral centroid
                plt.subplot(3, 1, 2)
                plt.plot(times, features['spectral_centroid'], label='Spectral Centroid', color='r')
                plt.ylabel('Hz')
                
                # Plot zero-crossing rate
                plt.subplot(3, 1, 3)
                plt.plot(times, features['zcr'], label='Zero Crossing Rate', color='g')
                plt.xlabel('Time (s)')
                plt.ylabel('Rate')
                
                # Save the plot
                plot_file = output_dir / 'audio_features.png'
                plt.tight_layout()
                plt.savefig(plot_file)
                plt.close()
                logger.info(f"Saved audio feature visualization to {plot_file}")
                
            except Exception as e:
                logger.warning(f"Could not create audio feature visualization: {e}")
        
        return {
            'status': 'success',
            'message': f'Detected {len(highlights)} highlights',
            'duration': float(duration),
            'highlights': highlights,
            'segment_count': len(context.segments) if hasattr(context, 'segments') else 0,
            'highlight_count': len(highlights),
            'audio_features': {
                'sample_rate': sample_rate,
                'hop_length': hop_length,
                'feature_count': len(features)
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

def create_highlight_video(
    input_path: Union[str, Path],
    segments: List[Dict[str, Any]],
    output_path: Union[str, Path],
    temp_dir: Optional[Union[str, Path]] = None
) -> str:
    """Create a highlight video from the given segments.
    
    Args:
        input_path: Path to the input video file
        segments: List of segment dictionaries with 'start' and 'end' times
        output_path: Path to save the output highlight video
        temp_dir: Directory for temporary files
        
    Returns:
        Path to the created highlight video
    """
    if not segments:
        raise ValueError("No segments provided for highlight video creation")
    
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="highlight_video_"))
    else:
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create a list of segment files
        segment_files = []
        
        for i, segment in enumerate(segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            if end <= start:
                logger.warning(f"Invalid segment {i}: end time {end} <= start time {start}")
                continue
                
            duration = end - start
            segment_file = temp_dir / f"segment_{i:04d}.mp4"
            
            # Extract segment using ffmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output files
                '-ss', str(start),
                '-i', str(input_path),
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict', 'experimental',
                '-b:a', '192k',
                '-movflags', '+faststart',
                str(segment_file)
            ]
            
            try:
                run_ffmpeg(cmd)
                segment_files.append(segment_file)
            except Exception as e:
                logger.error(f"Failed to extract segment {i}: {e}")
                continue
        
        if not segment_files:
            raise ValueError("No valid segments were extracted")
        
        # Create a file listing all segments for concatenation
        concat_file = temp_dir / 'concat_list.txt'
        with open(concat_file, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file.absolute()}'\n")
        
        # Concatenate all segments
        concat_output = temp_dir / 'concat_output.mp4'
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(concat_output)
        ]
        
        run_ffmpeg(cmd)
        
        # Copy the final output to the desired location
        shutil.copy2(concat_output, output_path)
        
        logger.info(f"Created highlight video at {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error creating highlight video: {e}")
        raise

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
        handlers=handlers
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
            
            # Create a list of segments to include in the highlight reel
            segments = [
                {
                    'start': h['start'],
                    'end': h['end'],
                    'file': str(input_path)
                }
                for h in highlights
            ]
            
            # Create highlight reel
            from app.editing.utils.video_utils import create_highlight_video
            output_video = create_highlight_video(
                input_path=str(input_path),
                highlights=highlights,
                output_path=str(output_path),
                temp_dir=temp_dir
            )
            
            logger.info(f"Highlight reel created at: {output_video}")
            print(f"\nSuccess! Created highlight reel at: {output_video}")
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
