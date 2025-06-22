import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging
from ..core.processor import VideoProcessor, VideoEditingError

logger = logging.getLogger(__name__)

class SilenceRemover(VideoProcessor):
    """Removes silent portions from the video."""
    
    def __init__(self, silence_threshold: float = -30.0, silence_duration: float = 0.5):
        """
        Initialize the silence remover.
        
        Args:
            silence_threshold: Volume threshold in dB below which audio is considered silent
            silence_duration: Minimum duration of silence to be removed (in seconds)
        """
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
    
    @property
    def name(self) -> str:
        return "silence_remover"
    
    def process(self, input_path: Path, output_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Remove silent portions from the video.
        
        Args:
            input_path: Path to the input video file
            output_path: Path where the processed video should be saved
            **kwargs: Additional parameters (not used)
            
        Returns:
            Dict containing processing results and metadata
        """
        logger.info(f"Removing silence from {input_path}")
        
        # First, detect silent sections
        silent_sections = self._detect_silence(input_path)
        
        if not silent_sections:
            logger.info("No silent sections found, copying input to output")
            self._copy_video(input_path, output_path)
            return {
                'status': 'completed',
                'silent_sections_found': 0,
                'total_silence_removed': 0.0
            }
        
        # Create a filter complex to cut out silent sections
        filter_complex = self._create_filter_complex(silent_sections)
        
        # Apply the filter using ffmpeg
        self._apply_filter(input_path, output_path, filter_complex)
        
        return {
            'status': 'completed',
            'silent_sections_found': len(silent_sections),
            'total_silence_removed': sum(end - start for start, end in silent_sections),
            'silent_sections': silent_sections
        }
    
    def _detect_silence(self, input_path: Path) -> list:
        """Detect silent sections in the audio."""
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-af', f'silencedetect=noise={self.silence_threshold}dB:d={self.silence_duration}',
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
            
            # Parse the output to find silent sections
            silent_sections = []
            lines = result.stderr.split('\n')
            
            for i, line in enumerate(lines):
                if 'silence_start' in line:
                    start = float(line.split(' ')[4])
                    # The next line should contain silence_end
                    if i + 1 < len(lines) and 'silence_end' in lines[i + 1]:
                        end = float(lines[i + 1].split(' ')[4].split('|')[0])
                        duration = end - start
                        if duration >= self.silence_duration:
                            silent_sections.append((start, end))
            
            return silent_sections
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error detecting silence: {e.stderr}")
            raise VideoEditingError(f"Failed to detect silence: {e.stderr}")
    
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
