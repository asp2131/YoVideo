"""Shared FFmpeg utilities for video processing."""
import subprocess
import logging
from typing import List, Optional

from ..core.processor import VideoEditingError

logger = logging.getLogger(__name__)

def run_ffmpeg(cmd: List[str], capture_stderr: bool = True) -> str:
    """
    Run an FFmpeg command and return stderr (for parsing).
    Raises VideoEditingError on failure.
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
            text=True,
            check=True,
            timeout=300
        )
        return result.stderr
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {' '.join(cmd)}\n{e.stderr}")
        raise VideoEditingError(f"FFmpeg command failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        error_msg = f"FFmpeg command timed out: {' '.join(cmd)}"
        logger.error(error_msg)
        raise VideoEditingError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error running FFmpeg: {str(e)}"
        logger.error(error_msg)
        raise VideoEditingError(error_msg)
