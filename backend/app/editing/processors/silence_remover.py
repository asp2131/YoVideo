"""Remove long silences from video while preserving natural speech pauses."""
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from dataclasses import dataclass
import tempfile
import shutil
import subprocess

from ..pipeline.core import (
    VideoProcessor, 
    Context, 
    PipelineError, 
    Progress, 
    CancellationToken, 
    ProcessingStatus
)

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
            error_msg = f"Silence removal failed: {str(e)}"
            logger.error(error_msg)
            
            # Update progress with error
            if progress_callback:
                progress_callback(Progress(
                    status=ProcessingStatus.FAILED,
                    message=error_msg,
                    current=0,
                    total=3
                ))
            
            raise PipelineError(error_msg) from e
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return 0.0
    
    def _detect_silence(self, video_path: str, cancel_token: CancellationToken) -> List[Dict[str, float]]:
        """Detect silent sections using ffmpeg."""
        try:
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Use ffmpeg to detect silence
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-af', f'silencedetect=noise={self.silence_threshold}dB:duration={self.silence_duration}',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse silence sections from stderr
            silence_sections = []
            lines = result.stderr.split('\n')
            
            current_silence = None
            for line in lines:
                if 'silence_start:' in line:
                    try:
                        start_time = float(line.split('silence_start:')[1].strip())
                        current_silence = {'start': start_time}
                    except (ValueError, IndexError):
                        continue
                elif 'silence_end:' in line and current_silence:
                    try:
                        end_time = float(line.split('silence_end:')[1].split()[0])
                        current_silence['end'] = end_time
                        silence_sections.append(current_silence)
                        current_silence = None
                    except (ValueError, IndexError):
                        continue
            
            return silence_sections
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg silence detection failed: {e.stderr}")
            return []
        except Exception as e:
            logger.error(f"Error detecting silence: {e}")
            return []
    
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
                metadata={'processor': 'SilenceRemover'}
            )
            progress_callback(progress)