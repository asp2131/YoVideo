"""Utility functions for video processing."""
import subprocess
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import json
import os

logger = logging.getLogger(__name__)

def get_video_info(input_path: Path) -> Dict[str, Any]:
    """
    Get detailed information about a video file using ffprobe.
    
    Args:
        input_path: Path to the video file
        
    Returns:
        Dictionary containing video information
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(input_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        info = json.loads(result.stdout)
        
        # Extract basic information
        video_info = {
            'duration': float(info['format'].get('duration', 0)),
            'format': info['format'].get('format_name', ''),
            'size': int(info['format'].get('size', 0)),
            'bit_rate': int(info['format'].get('bit_rate', 0)),
            'streams': []
        }
        
        # Extract stream information
        for stream in info.get('streams', []):
            stream_info = {
                'codec_type': stream.get('codec_type', ''),
                'codec_name': stream.get('codec_name', ''),
                'codec_long_name': stream.get('codec_long_name', ''),
                'width': stream.get('width'),
                'height': stream.get('height'),
                'sample_rate': stream.get('sample_rate'),
                'channels': stream.get('channels'),
                'channel_layout': stream.get('channel_layout', ''),
                'bit_rate': stream.get('bit_rate'),
                'duration': stream.get('duration')
            }
            video_info['streams'].append(stream_info)
        
        return video_info
        
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error getting video info: {e}")
        return {}

def extract_audio(
    input_path: Path,
    output_path: Path,
    format: str = 'wav',
    sample_rate: int = 16000,
    channels: int = 1
) -> bool:
    """
    Extract audio from a video file.
    
    Args:
        input_path: Path to the input video file
        output_path: Path where the audio will be saved
        format: Output audio format (wav, mp3, etc.)
        sample_rate: Output sample rate in Hz
        channels: Number of audio channels
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-vn',
        '-acodec', 'pcm_s16le' if format == 'wav' else 'copy',
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-y',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error extracting audio: {e.stderr}")
        return False

def get_audio_levels(input_path: Path, window_size: float = 0.1) -> List[float]:
    """
    Get audio volume levels over time.
    
    Args:
        input_path: Path to the audio file
        window_size: Time window in seconds for each volume sample
        
    Returns:
        List of volume levels in dB
    """
    # First, extract audio to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
        temp_audio_path = Path(temp_audio.name)
        
        if not extract_audio(input_path, temp_audio_path):
            return []
            
        try:
            # Use ffmpeg to analyze audio levels
            cmd = [
                'ffmpeg',
                '-i', str(temp_audio_path),
                '-af', f'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
                '-f', 'null',
                '-',
                '-y'
            ]
            
            result = subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Parse the output to get volume levels
            levels = []
            for line in result.stderr.split('\n'):
                if 'lavfi.astats.Overall.RMS_level' in line:
                    try:
                        # Extract the dB value (e.g., "-42.5 dB" -> -42.5)
                        db_str = line.split('=')[1].strip().split()[0]
                        levels.append(float(db_str))
                    except (IndexError, ValueError):
                        continue
            
            return levels
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting audio levels: {e.stderr}")
            return []
        finally:
            # Clean up the temporary file
            if temp_audio_path.exists():
                temp_audio_path.unlink()

def create_video_from_images(
    image_pattern: str,
    output_path: Path,
    frame_rate: float = 30.0,
    crf: int = 23,
    preset: str = 'medium'
) -> bool:
    """
    Create a video from a sequence of images.
    
    Args:
        image_pattern: Pattern for input images (e.g., 'frame_%04d.png')
        output_path: Path where the output video will be saved
        frame_rate: Output frame rate
        crf: Constant Rate Factor (lower = better quality, 18-28 is a good range)
        preset: Encoding preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg',
        '-framerate', str(frame_rate),
        '-i', image_pattern,
        '-c:v', 'libx264',
        '-profile:v', 'high',
        '-crf', str(crf),
        '-preset', preset,
        '-pix_fmt', 'yuv420p',
        '-y',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating video from images: {e.stderr}")
        return False

def concat_videos(
    input_files: List[Path],
    output_path: Path,
    temp_dir: Optional[Path] = None
) -> bool:
    """
    Concatenate multiple video files.
    
    Args:
        input_files: List of input video files
        output_path: Path where the concatenated video will be saved
        temp_dir: Optional directory for temporary files
        
    Returns:
        True if successful, False otherwise
    """
    if not input_files:
        logger.warning("No input files provided for concatenation")
        return False
    
    # If only one file, just copy it
    if len(input_files) == 1:
        import shutil
        shutil.copy2(input_files[0], output_path)
        return True
    
    # Create a temporary directory if not provided
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="concat_temp_"))
    else:
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create a file list for ffmpeg concat
        file_list = temp_dir / "file_list.txt"
        with open(file_list, 'w') as f:
            for video_file in input_files:
                f.write(f"file '{video_file.absolute()}'\n")
        
        # Run ffmpeg concat
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(file_list),
            '-c', 'copy',
            '-y',
            str(output_path)
        ]
        
        logger.info(f"Concatenating {len(input_files)} videos to {output_path}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error concatenating videos: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in concat_videos: {str(e)}")
        return False

def extract_segments(
    input_path: Path,
    segments: List[Dict[str, float]],
    output_path: Optional[Path] = None,
    temp_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Extract segments from a video file.
    
    Args:
        input_path: Path to the input video file
        segments: List of segment dictionaries with 'start' and 'end' times in seconds
        output_path: Path where the output video will be saved (optional)
        temp_dir: Directory for temporary files (optional)
        
    Returns:
        Path to the output video file if successful, None otherwise
    """
    if not segments:
        logger.warning("No segments provided for extraction")
        return None
    
    # Create output path if not provided
    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_highlights")
    
    # Create temp directory if not provided
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="extract_segments_"))
    else:
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        segment_files = []
        
        # Extract each segment
        for i, segment in enumerate(segments):
            start = segment['start']
            duration = segment['end'] - start
            segment_path = temp_dir / f"segment_{i:04d}{input_path.suffix}"
            
            cmd = [
                'ffmpeg',
                '-ss', str(start),
                '-i', str(input_path),
                '-t', str(duration),
                '-c', 'copy',
                '-y',
                str(segment_path)
            ]
            
            logger.info(f"Extracting segment {i+1}: {start:.2f}s - {segment['end']:.2f}s")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            segment_files.append(segment_path)
        
        # If only one segment, just rename it
        if len(segment_files) == 1:
            segment_files[0].replace(output_path)
            return output_path
        
        # Otherwise, concatenate the segments
        if concat_videos(segment_files, output_path, temp_dir):
            return output_path
        return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error extracting segments: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in extract_segments: {str(e)}")
        return None
