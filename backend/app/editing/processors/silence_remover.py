"""Remove long silences from video while preserving natural speech pauses."""
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from dataclasses import dataclass
import tempfile
import shutil

from ..pipeline.core import (
    VideoProcessor, 
    Context, 
    PipelineError, 
    Progress, 
    CancellationToken, 
    ProcessingStatus
)
from ..utils.ffmpeg_utils import run_ffmpeg

logger = logging.getLogger(__name__)

@dataclass
class SilenceSection:
    """Represents a silent section in the audio."""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    
    @property
    def duration(self) -> float:
        return self.end - self.start

class SilenceRemover(VideoProcessor):
    """Strip only long (> threshold) silences, preserving natural speech pauses."""
    
    def __init__(self, silence_threshold: float = -30.0, silence_duration: float = 0.8):
        """Initialize the silence remover.
        
        Args:
            silence_threshold: Volume threshold in dB below which audio is considered silent
            silence_duration: Minimum duration in seconds for a silent section to be detected
        """
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration

    @property
    def name(self) -> str:
        return "silence_remover"
    
    def process(
        self, 
        context: Context, 
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """Remove long silences from the video.
        
        Args:
            context: The processing context
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with silent sections marked and video processed
            
        Raises:
            PipelineError: If silence removal fails
        """
        # Initialize cancellation
        cancel_token = cancel_token or CancellationToken()
        
        try:
            # Update progress
            self._update_progress(progress_callback, 0, 3, ProcessingStatus.RUNNING, 
                                "Starting silence detection")
            
            logger.info(f"Detecting silent sections with threshold={self.silence_threshold}dB, "
                     f"min_duration={self.silence_duration}s")
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Step 1: Get video duration
            self._update_progress(progress_callback, 1, 3, 
                                message="Getting video duration")
            
            duration = self._get_video_duration(context.video_path)
            if duration:
                context.duration = duration
                logger.info(f"Video duration: {duration:.2f}s")
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Step 2: Detect silence using ffmpeg
            self._update_progress(progress_callback, 2, 3, 
                                message="Detecting silent sections")
            
            silence_sections = self._detect_silence(
                context.video_path, 
                cancel_token
            )
            
            # Store silence sections in context
            context.silence_sections = silence_sections
            
            logger.info(f"Detected {len(silence_sections)} silent sections in {context.duration:.2f}s video")
            
            # Mark as complete
            self._update_progress(progress_callback, 3, 3, ProcessingStatus.COMPLETED, 
                                "Silence detection complete")
            
            return context
            
        except Exception as e:
            # Clean up the temporary file if it exists
            if output_path.exists():
                output_path.unlink()
            error_msg = f"Silence removal failed: {str(e)}"
            logger.error(error_msg)
            
            # Update progress with error
            if progress_callback:
                progress_callback(Progress(
                    status=ProcessingStatus.FAILED,
                    message=error_msg,
                    progress=0.0
                ))
            
            raise PipelineError(error_msg) from e
    
    def _apply_filter(self, input_path: Path, output_path: Path, filter_complex: str) -> None:
        """Apply the filter complex to the input video."""
        if not filter_complex:
            self._copy_video(input_path, output_path)
            return
            
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-strict', 'experimental',
            '-y',
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error applying filter: {e.stderr}")
            raise VideoEditingError(f"Failed to apply filter: {e.stderr}")
    
    @staticmethod
    def _copy_video(src: Path, dst: Path) -> None:
        """Copy a video file from src to dst."""
        import shutil
        shutil.copy2(src, dst)
