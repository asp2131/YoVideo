import subprocess
import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
import tempfile
import shutil

from ..core.processor import VideoProcessor, VideoEditingError

logger = logging.getLogger(__name__)

class SceneDetector(VideoProcessor):
    """Detects scene changes in a video."""
    
    def __init__(self, threshold: float = 30.0, min_scene_len: float = 1.5):
        """
        Initialize the scene detector.
        
        Args:
            threshold: Threshold for scene change detection (lower = more sensitive)
            min_scene_len: Minimum length of a scene in seconds
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len
    
    @property
    def name(self) -> str:
        return "scene_detector"
    
    def process(self, input_path: Path, output_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Detect scenes in the video.
        
        Args:
            input_path: Path to the input video file
            output_path: Path where the scene information will be saved as JSON
            **kwargs: Additional parameters
                - output_video: If True, creates a visualization of scene cuts
        """
        logger.info(f"Detecting scenes in {input_path}")
        
        # Get video duration
        duration = self._get_video_duration(input_path)
        if duration <= 0:
            raise VideoEditingError(f"Invalid video duration: {duration}")
        
        # Detect scenes using ffmpeg's select filter
        scenes = self._detect_scenes(input_path)
        
        # Filter out very short scenes
        scenes = self._filter_short_scenes(scenes, duration)
        
        # Save scene information
        scene_info = {
            'total_scenes': len(scenes),
            'duration': duration,
            'scenes': [{'start': start, 'end': end} for start, end in scenes]
        }
        
        with open(output_path, 'w') as f:
            json.dump(scene_info, f, indent=2)
        
        # Optionally create a visualization
        if kwargs.get('output_video'):
            self._create_scene_visualization(input_path, output_path.with_suffix('.mp4'), scenes)
        
        return scene_info
    
    def _get_video_duration(self, input_path: Path) -> float:
        """Get the duration of the input video in seconds."""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(input_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Error getting video duration: {e}")
            return 0.0
    
    def _detect_scenes(self, input_path: Path) -> List[Tuple[float, float]]:
        """Detect scene changes using ffmpeg's select filter."""
        # First pass: detect scene changes
        scene_changes = [0.0]
        
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-filter_complex', f"select='gt(scene,{self.threshold}/100)',metadata=print:file=-",
            '-f', 'null',
            '-',
            '-y'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Parse the output to find scene change timestamps
            for line in result.stderr.split('\n'):
                if 'pts_time:' in line:
                    try:
                        timestamp = float(line.split('pts_time:')[-1].strip())
                        scene_changes.append(timestamp)
                    except (ValueError, IndexError):
                        continue
            
            # Add the end of the video as the final scene change
            duration = self._get_video_duration(input_path)
            if duration > 0:
                scene_changes.append(duration)
            
            # Convert to (start, end) pairs
            scenes = list(zip(scene_changes[:-1], scene_changes[1:]))
            
            return scenes
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error detecting scenes: {e.stderr}")
            raise VideoEditingError(f"Failed to detect scenes: {e.stderr}")
    
    def _filter_short_scenes(self, scenes: List[Tuple[float, float]], duration: float) -> List[Tuple[float, float]]:
        """Filter out scenes that are too short."""
        if not scenes:
            return [(0.0, duration)]
        
        filtered_scenes = []
        
        for i, (start, end) in enumerate(scenes):
            scene_duration = end - start
            if scene_duration >= self.min_scene_len:
                filtered_scenes.append((start, end))
            else:
                # Merge with previous or next scene if too short
                if i > 0 and filtered_scenes:
                    prev_start, prev_end = filtered_scenes[-1]
                    filtered_scenes[-1] = (prev_start, end)
                elif i < len(scenes) - 1:
                    next_start, next_end = scenes[i + 1]
                    filtered_scenes.append((start, next_end))
        
        return filtered_scenes or [(0.0, duration)]
    
    def _create_scene_visualization(self, input_path: Path, output_path: Path, scenes: List[Tuple[float, float]]) -> None:
        """Create a visualization of the scene cuts."""
        if not scenes:
            return
        
        # Create a temporary directory for scene thumbnails
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Generate thumbnails for each scene
            for i, (start, _) in enumerate(scenes):
                thumb_path = temp_dir_path / f"scene_{i:04d}.jpg"
                self._extract_thumbnail(input_path, thumb_path, start)
            
            # Create a montage of the thumbnails
            self._create_montage(temp_dir_path, output_path, len(scenes))
    
    def _extract_thumbnail(self, input_path: Path, output_path: Path, timestamp: float) -> None:
        """Extract a thumbnail at the given timestamp."""
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp),
            '-i', str(input_path),
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error extracting thumbnail at {timestamp}: {e.stderr}")
    
    def _create_montage(self, thumb_dir: Path, output_path: Path, num_scenes: int) -> None:
        """Create a montage of scene thumbnails."""
        # Create a text file with the list of thumbnails
        list_file = thumb_dir / "thumbs.txt"
        with open(list_file, 'w') as f:
            for i in range(num_scenes):
                thumb_path = thumb_dir / f"scene_{i:04d}.jpg"
                if thumb_path.exists():
                    f.write(f"file '{thumb_path}'\n")
        
        # Create the montage
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(list_file),
            '-vf', 'tile=5x1',
            '-y',
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating scene montage: {e.stderr}")
