import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from dataclasses import dataclass
from ..pipeline.core import VideoProcessor, Context, PipelineError, Progress, CancellationToken, ProcessingStatus

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
    """Detects silent sections in the audio track."""
    
    def __init__(self, silence_threshold: float = -30.0, silence_duration: float = 0.5):
        """Initialize the silence remover.
        
        Args:
            silence_threshold: Volume threshold in dB below which audio is considered silent
            silence_duration: Minimum duration in seconds for a silent section to be detected
        """
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
    
    def process(
        self, 
        context: Context, 
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """Detect silent sections in the audio track.
        
        Args:
            context: The processing context
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with silence sections marked
            
        Raises:
            PipelineError: If silence detection fails
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
            error_msg = f"Error detecting silence: {str(e)}"
            self._update_progress(progress_callback, 0, 3, ProcessingStatus.FAILED, error_msg)
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(error_msg) from e
    
    def _detect_silence(self, video_path: str, cancel_token: CancellationToken) -> List[Dict[str, float]]:
        """Detect silent sections in the video using ffmpeg."""
        try:
            # Use ffmpeg's silencedetect filter to find silent sections
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-af', f'silencedetect=noise={self.silence_threshold}dB:d={self.silence_duration}',
                '-f', 'null',
                '-',
                '-y',
                '-loglevel', 'info+repeat+level+verbose+cmd+debug'
            ]
            
            # Run the command and capture stderr (where silencedetect outputs its data)
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            output = []
            
            # Read output line by line to allow for cancellation
            while True:
                if cancel_token.is_cancelled:
                    process.terminate()
                    raise PipelineError("Silence detection was cancelled")
                
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                    
                if line:
                    output.append(line)
            
            # Check return code
            if process.returncode != 0:
                logger.warning(f"FFmpeg returned non-zero exit code {process.returncode}")
                return []
            
            # Parse the output to find silence sections
            return self._parse_silence_output(''.join(output))
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"FFmpeg error: {str(e)}")
            return []
    
    def _parse_silence_output(self, output: str) -> List[Dict[str, float]]:
        """Parse ffmpeg's silencedetect output into a list of silence sections."""
        import re
        
        # This regex matches the silence_start and silence_end lines from ffmpeg's output
        silence_start_re = r'silence_start: (\d+(?:\.\d+)?)'
        silence_end_re = r'silence_end: (\d+(?:\.\d+)?)'
        
        starts = [float(match) for match in re.findall(silence_start_re, output)]
        ends = [float(match) for match in re.findall(silence_end_re, output)]
        
        # Pair up starts and ends
        silence_sections = [
            {'start': start, 'end': end, 'duration': end - start}
            for start, end in zip(starts, ends)
        ]
        
        return silence_sections
    
    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """Get video duration using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            return float(result.stdout.strip())
            
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Could not determine video duration: {str(e)}")
            return None
    
    def _update_progress(
        self,
        progress_callback: Optional[Callable[[Progress], None]],
        current: int,
        total: int,
        status: ProcessingStatus = ProcessingStatus.RUNNING,
        message: str = ""
    ) -> None:
        """Helper method to update progress if callback is provided."""
        if progress_callback:
            progress = Progress(
                current=current,
                total=total,
                status=status,
                message=message,
                metadata={
                    'processor': self.__class__.__name__,
                    'silence_threshold': self.silence_threshold,
                    'silence_duration': self.silence_duration
                }
            )
            progress_callback(progress)
    
    def _create_filter_complex(self, silent_sections: list) -> str:
        """Create a filter complex to remove silent sections."""
        if not silent_sections:
            return ""
            
        # Sort sections by start time
        silent_sections.sort()
        
        # Build the filter complex
        filter_parts = []
        last_end = 0.0
        
        for i, (start, end) in enumerate(silent_sections):
            if start > last_end:
                # Add the segment before this silence
                filter_parts.append(f"between(t,{last_end},{start})")
            last_end = end
        
        # Add the final segment after the last silence
        filter_parts.append(f"gt(t,{last_end})")
        
        return "select='" + "+".join(filter_parts) + "',setpts=N/FRAME_RATE/TB"
    
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
