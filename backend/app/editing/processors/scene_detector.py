"""Scene change detection using FFmpeg's scene filter."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..pipeline.core import VideoProcessor, Context, PipelineError
from ..utils.ffmpeg_utils import run_ffmpeg

logger = logging.getLogger(__name__)

@dataclass
class SceneChange:
    """Represents a scene change in the video."""
    time: float  # Time in seconds where the scene changes
    score: float = 1.0  # Confidence score (1.0 for FFmpeg's scene detection)

class SceneDetector(VideoProcessor):
    """Detects scene changes using FFmpeg's scene filter."""

    def __init__(self, threshold: float = 0.3, min_scene_len: float = 1.5):
        """
        Initialize the scene detector.
        
        Args:
            threshold: Threshold for scene change detection (0-1, lower = more sensitive)
            min_scene_len: Minimum length of a scene in seconds
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len

    @property
    def name(self) -> str:
        return "scene_detector"
    
    def process(self, context: Context) -> Context:
        """
        Detect scene changes in the video and add them to the context.
        
        Args:
            context: The processing context containing video path and other state
            
        Returns:
            Updated context with scene changes
            
        Raises:
            PipelineError: If scene detection fails
        """
        video_path = Path(context.video_path)
        logger.info(f"Detecting scene changes in {video_path}")
        
        # Run FFmpeg to detect scene changes
        raw_output = run_ffmpeg([
            "ffmpeg", "-i", str(video_path),
            "-filter_complex",
            f"select='gt(scene,{self.threshold})',metadata=print",
            "-f", "null", "-"
        ])
        
        # Parse timestamps from FFmpeg output
        times = [0.0]
        for line in raw_output.splitlines():
            if "pts_time:" in line:
                try:
                    times.append(float(line.split("pts_time:")[-1]))
                except ValueError:
                    continue
        
        # Add end time if duration is available
        duration = getattr(context, 'duration', None)
        if duration is None:
            duration = self._probe_duration(video_path)
        times.append(duration)
        
        # Build and filter scenes
        scenes = []
        for a, b in zip(times, times[1:]):
            if b - a >= self.min_scene_len:
                scenes.append(SceneChange(time=a, score=1.0))
            elif scenes:
                # Merge short scenes into the previous one
                scenes[-1] = SceneChange(time=scenes[-1].time, score=scenes[-1].score)
        
        # Add final scene change
        if scenes and scenes[-1].time < duration:
            scenes.append(SceneChange(time=duration, score=1.0))
        
        # Update context
        context.scene_changes = scenes
        context.scenes = [(s.time, e.time) for s, e in zip(scenes, scenes[1:])]
        
        logger.info(f"Detected {len(scenes)} scene changes")
        return context
    
    def _probe_duration(self, video_path: Path) -> float:
        """Get video duration using FFprobe."""
        try:
            raw = run_ffmpeg([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ], capture_stderr=False)
            return float(raw.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            raise PipelineError(f"Could not determine video duration: {e}")
            # Filter out very short scenes
            filtered_changes = self._filter_short_scenes(scene_changes, duration)
            
            # Store in context (convert to list of timestamps for backward compatibility)
            context.scene_changes = [change.time for change in filtered_changes]
            
            # Also store full scene change objects if needed
            context.metadata['scene_changes_detailed'] = [
                {'time': c.time, 'score': c.score} for c in filtered_changes
            ]
            
            logger.info(f"Detected {len(filtered_changes)} scene changes")
            return context
            
        except Exception as e:
            raise PipelineError(f"Scene detection failed: {str(e)}") from e
    
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
