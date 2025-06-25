"""Scene change detection using FFmpeg's scene filter."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import subprocess

from ..pipeline.core import VideoProcessor, Context, PipelineError, Progress, ProcessingStatus, CancellationToken

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
    
    def process(
        self, 
        context: Context,
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """
        Detect scene changes in the video and add them to the context.
        
        Args:
            context: The processing context containing video path and other state
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with scene changes
            
        Raises:
            PipelineError: If scene detection fails
        """
        cancel_token = cancel_token or CancellationToken()
        
        try:
            # Update progress
            self._update_progress(progress_callback, 0, 3, ProcessingStatus.RUNNING,
                                "Starting scene detection")
            
            video_path = Path(context.video_path)
            logger.info(f"Detecting scene changes in {video_path}")
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Step 1: Get video duration
            self._update_progress(progress_callback, 1, 3, message="Getting video duration")
            duration = self._probe_duration(video_path)
            if not hasattr(context, 'duration') or not context.duration:
                context.duration = duration
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Step 2: Detect scene changes
            self._update_progress(progress_callback, 2, 3, message="Detecting scene changes")
            scene_changes = self._detect_scenes(video_path)
            
            # Update context
            context.scene_changes = [change.time for change in scene_changes]
            
            # Also store detailed scene change objects in metadata
            context.metadata['scene_changes_detailed'] = [
                {'time': c.time, 'score': c.score} for c in scene_changes
            ]
            
            # Mark as complete
            self._update_progress(progress_callback, 3, 3, ProcessingStatus.COMPLETED,
                                f"Detected {len(scene_changes)} scene changes")
            
            logger.info(f"Detected {len(scene_changes)} scene changes")
            return context
            
        except Exception as e:
            error_msg = f"Scene detection failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if progress_callback:
                progress_callback(Progress(
                    status=ProcessingStatus.FAILED,
                    message=error_msg
                ))
            
            raise PipelineError(error_msg) from e
    
    def _probe_duration(self, video_path: Path) -> float:
        """Get video duration using FFprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            raise PipelineError(f"Could not determine video duration: {e}")
    
    def _detect_scenes(self, video_path: Path) -> List[SceneChange]:
        """Detect scene changes using FFmpeg's scene filter."""
        try:
            # Run FFmpeg to detect scene changes
            cmd = [
                "ffmpeg", "-i", str(video_path),
                "-filter_complex",
                f"select='gt(scene,{self.threshold})',metadata=print",
                "-f", "null", "-"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse timestamps from FFmpeg output
            times = [0.0]  # Always start with time 0
            for line in result.stderr.split('\n'):
                if "pts_time:" in line:
                    try:
                        time_str = line.split("pts_time:")[-1].strip()
                        timestamp = float(time_str)
                        times.append(timestamp)
                    except ValueError:
                        continue
            
            # Filter out very short scenes
            filtered_times = [times[0]]  # Always keep the first timestamp
            for i in range(1, len(times)):
                if times[i] - filtered_times[-1] >= self.min_scene_len:
                    filtered_times.append(times[i])
            
            # Convert to SceneChange objects
            scene_changes = [SceneChange(time=t, score=1.0) for t in filtered_times]
            
            return scene_changes
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg scene detection failed: {e.stderr}")
            # Return at least one scene change at the beginning
            return [SceneChange(time=0.0, score=1.0)]
        except Exception as e:
            logger.error(f"Error detecting scenes: {e}")
            # Return at least one scene change at the beginning
            return [SceneChange(time=0.0, score=1.0)]
    
    def _update_progress(
        self,
        progress_callback: Optional[Callable[[Progress], None]],
        current: int,
        total: int,
        status: ProcessingStatus = ProcessingStatus.RUNNING,
        message: str = ""
    ):
        """Update progress if callback is provided."""
        if progress_callback:
            progress = Progress(
                current=current,
                total=total,
                status=status,
                message=message,
                metadata={'processor': 'SceneDetector'}
            )
            progress_callback(progress)