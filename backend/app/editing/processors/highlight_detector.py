"""
Highlight Detector for Video Processing

This module provides functionality to detect and remove silent segments from videos,
creating more engaging content by focusing on the most relevant parts.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydub import AudioSegment, silence

from app.editing.core.processor import VideoProcessor

logger = logging.getLogger(__name__)

class HighlightDetector(VideoProcessor):
    """
    A processor that identifies and removes silent segments from videos.
    
    This detector focuses on audio analysis to find and remove silent portions,
    making it ideal for creating more engaging video highlights.
    """
    
    def __init__(
        self,
        min_duration: float = 3.0,           # Minimum highlight duration in seconds
        max_duration: float = 15.0,          # Maximum highlight duration in seconds
        min_silence_len: int = 500,          # Minimum silence length in ms to consider for cutting
        silence_thresh: int = -40,           # Silence threshold in dB (lower = more sensitive)
        keep_silence: int = 200,             # Keep this much silence around cuts (ms)
    ):
        """
        Initialize the highlight detector with processing parameters.
        
        Args:
            min_duration: Minimum duration of a highlight segment in seconds
            max_duration: Maximum duration of a highlight segment in seconds
            min_silence_len: Minimum silence length in milliseconds to detect for cuts
            silence_thresh: Silence threshold in dB (lower values make it more sensitive)
            keep_silence: How much silence to keep around cuts in milliseconds
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.min_silence_len = min_silence_len
        self.silence_thresh = silence_thresh
        self.keep_silence = keep_silence
    
    @property
    def name(self) -> str:
        """Return the name identifier for this processor."""
        return "highlight_detector"
    
    def _invert_silent_segments(
        self, 
        silent_segments: List[Dict], 
        total_duration: float
    ) -> List[Dict]:
        """
        Convert silent segments into segments to keep.
        
        Args:
            silent_segments: List of silent segments with 'start' and 'end' times
            total_duration: Total duration of the video in seconds
            
        Returns:
            List of segments to keep (non-silent)
        """
        logger.info(f"Inverting {len(silent_segments)} silent segments (total duration: {total_duration:.2f}s)")
        logger.info(f"Min duration: {self.min_duration:.2f}s, Max duration: {self.max_duration:.2f}s")
        
        if not silent_segments:
            logger.info("No silent segments found, keeping entire video")
            return [{"start": 0.0, "end": total_duration, "type": "full_video"}]
        
        # Sort silent segments by start time
        silent_segments.sort(key=lambda x: x.get("start", 0))
        
        # Log all silent segments
        for i, seg in enumerate(silent_segments, 1):
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            logger.debug(f"Silent segment {i}: {seg_start:.2f}s - {seg_end:.2f}s (duration: {seg_end - seg_start:.2f}s)")
        
        # Find the non-silent segments (gaps between silent segments)
        keep_segments = []
        prev_end = 0.0
        
        # Process each gap between silent segments
        for i, seg in enumerate(silent_segments, 1):
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            gap = seg_start - prev_end
            
            logger.debug(f"Gap {i}: {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s)")
            
            # Add segment before this silent period if it's long enough
            if gap > 0:  # Only process positive gaps
                if gap >= self.min_duration:
                    logger.debug(f"  KEEPING segment: {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s)")
                    keep_segments.append({
                        "start": prev_end,
                        "end": seg_start,
                        "type": "gap",
                        "duration": gap
                    })
                else:
                    logger.debug(f"  SKIPPING segment (too short): {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s < {self.min_duration:.2f}s)")
            
            prev_end = seg_end
        
        # Add final segment if applicable
        final_gap = total_duration - prev_end
        if final_gap > 0:  # Only process if there's actually content after the last silent segment
            if final_gap >= self.min_duration:
                logger.debug(f"KEEPING final segment: {prev_end:.2f}s - {total_duration:.2f}s (duration: {final_gap:.2f}s)")
                keep_segments.append({
                    "start": prev_end,
                    "end": total_duration,
                    "type": "final",
                    "duration": final_gap
                })
            else:
                logger.debug(f"SKIPPING final segment (too short): {prev_end:.2f}s - {total_duration:.2f}s (duration: {final_gap:.2f}s < {self.min_duration:.2f}s)")
        
        # If no segments meet the minimum duration, try to find the longest segment
        if not keep_segments and silent_segments:
            logger.warning("No segments meet the minimum duration. Trying to find the longest segment...")
            
            # Find the longest gap between silent segments
            max_gap = 0
            best_segment = None
            
            # Check gaps between silent segments
            for i in range(1, len(silent_segments)):
                gap = silent_segments[i]["start"] - silent_segments[i-1]["end"]
                if gap > max_gap:
                    max_gap = gap
                    best_segment = {
                        "start": silent_segments[i-1]["end"],
                        "end": silent_segments[i]["start"],
                        "type": "longest_gap"
                    }
            
            # Check gap at the beginning
            first_gap = silent_segments[0]["start"] - 0
            if first_gap > max_gap:
                max_gap = first_gap
                best_segment = {
                    "start": 0.0,
                    "end": silent_segments[0]["start"],
                    "type": "longest_gap"
                }
            
            # Check gap at the end
            last_gap = total_duration - silent_segments[-1]["end"]
            if last_gap > max_gap:
                max_gap = last_gap
                best_segment = {
                    "start": silent_segments[-1]["end"],
                    "end": total_duration,
                    "type": "longest_gap"
                }
            
            if best_segment:
                duration = best_segment["end"] - best_segment["start"]
                logger.warning(f"Using longest gap found: {best_segment['start']:.2f}s - {best_segment['end']:.2f}s (duration: {duration:.2f}s)")
                keep_segments.append(best_segment)
            else:
                logger.warning("No valid segments found, defaulting to first segment")
                first_seg = silent_segments[0]
                keep_segments.append({
                    "start": 0.0,
                    "end": min(5.0, total_duration),  # Default to first 5 seconds or total duration if shorter
                    "type": "default"
                })
        
        logger.info(f"Found {len(keep_segments)} segments before max duration check")
        
        # Ensure segments don't exceed max duration
        result = []
        for seg in keep_segments:
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            
            if duration > self.max_duration:
                # Split long segments into max_duration chunks
                num_chunks = int(duration // self.max_duration) + 1
                chunk_duration = duration / num_chunks
                logger.debug(f"Splitting long segment ({duration:.2f}s) into {num_chunks} chunks of ~{chunk_duration:.2f}s")
                
                for i in range(num_chunks):
                    chunk_start = start + i * chunk_duration
                    chunk_end = min(start + (i + 1) * chunk_duration, end)
                    chunk = {
                        "start": chunk_start,
                        "end": chunk_end,
                        "type": f"split_{i+1}_of_{num_chunks}",
                        "duration": chunk_end - chunk_start
                    }
                    result.append(chunk)
                    logger.debug(f"  Created chunk: {chunk['start']:.2f}s - {chunk['end']:.2f}s (duration: {chunk['duration']:.2f}s)")
            else:
                seg["duration"] = duration
                result.append(seg)
        
        # Log final segments
        logger.info(f"Returning {len(result)} segments after max duration check")
        total_duration = sum(seg.get("duration", 0) for seg in result)
        logger.info(f"Total duration of all segments: {total_duration:.2f}s")
        
        for i, seg in enumerate(result, 1):
            seg_duration = seg.get("duration", seg.get("end", 0) - seg.get("start", 0))
            logger.info(f"  Segment {i}: {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s (duration: {seg_duration:.2f}s) [{seg.get('type', 'normal')}]")
        
        return result
        
    def process(self, input_path: Path, output_path: Path, **kwargs) -> Dict:
        """
        Process a video to detect and remove silent segments.
        
        Args:
            video_path: Path to the video file
            video_info: Dictionary containing video metadata
            
        Returns:
            Dictionary containing:
                - status: "success" or "error"
                - segments: List of segments to keep
                - total_duration: Total duration of the original video
                - message: Error message if status is "error"
        """
        logger.info(f"Detecting silent segments in {input_path}")
        
        try:
            # Get video info from kwargs or get it ourselves
            video_info = kwargs.get('video_info', {})
            if not video_info:
                logger.info("No video_info provided in kwargs, getting video info...")
                from ..utils.video_utils import get_video_info
                video_info = get_video_info(input_path)
                logger.info(f"Retrieved video info: {video_info}")
            else:
                logger.info(f"Using provided video info: {video_info}")
            
            # Ensure we have a valid duration
            if 'duration' not in video_info or not video_info['duration']:
                raise ValueError("Could not determine video duration")
            
            logger.info(f"Video duration: {video_info['duration']:.2f} seconds")
            
            # Detect silent segments
            logger.info("Detecting silent segments...")
            silent_segments = self._detect_silent_segments(input_path)
            logger.info(f"Detected {len(silent_segments)} silent segments")
            
            # Convert silent segments to keep segments (invert the selection)
            logger.info("Inverting silent segments to get keep segments...")
            keep_segments = self._invert_silent_segments(
                silent_segments, 
                video_info.get('duration', 0)
            )
            logger.info(f"Found {len(keep_segments)} segments to keep")
            
            # If there's an output path, process the video to extract highlights
            if output_path:
                if keep_segments:
                    logger.info(f"Extracting {len(keep_segments)} segments to {output_path}")
                    from ..utils.video_utils import extract_segments
                    try:
                        extract_segments(
                            input_path=input_path,
                            segments=keep_segments,
                            output_path=output_path
                        )
                        logger.info("Successfully extracted segments")
                    except Exception as e:
                        logger.error(f"Error extracting segments: {e}", exc_info=True)
                        raise
                else:
                    logger.warning("No segments to extract, skipping video extraction")
            
            return {
                "status": "success" if keep_segments else "no_highlights",
                "segments": keep_segments,
                "total_duration": video_info.get('duration', 0),
                "message": "No highlight segments found" if not keep_segments else None
            }
        
        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "segments": [],
                "total_duration": 0
            }
    
    def _detect_silent_segments(self, video_path: Path) -> List[Dict]:
        """
        Detect silent segments in the audio using pydub's silence detection.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            List of silent segments with 'start' and 'end' times in seconds
        """
        try:
            logger.info(f"Loading audio from {video_path}")
            # Load audio using pydub
            audio = AudioSegment.from_file(str(video_path))
            
            # Log audio properties
            logger.info(f"Audio properties: {len(audio)}ms, {audio.channels} channels, {audio.frame_rate}Hz, {audio.sample_width*8}-bit")
            
            # Log detection parameters
            logger.info(f"Detection parameters: min_silence_len={self.min_silence_len}ms, "
                       f"silence_thresh={self.silence_thresh}dB, keep_silence={self.keep_silence}ms")
            
            # Detect silent chunks (ensure all parameters are integers)
            silent_chunks = silence.detect_silence(
                audio,
                min_silence_len=int(self.min_silence_len),
                silence_thresh=int(self.silence_thresh),
                seek_step=10  # 10ms step for better precision
            )
            
            logger.info(f"Found {len(silent_chunks)} silent chunks")
            
            # Convert from ms to seconds and adjust with keep_silence
            silent_segments = []
            for i, (start, end) in enumerate(silent_chunks, 1):
                # Convert from ms to seconds
                start_sec = start / 1000.0
                end_sec = end / 1000.0
                
                # Apply keep_silence adjustment (convert to seconds)
                start_adj = max(0, start_sec - (self.keep_silence / 1000.0))
                end_adj = min(len(audio) / 1000.0, end_sec + (self.keep_silence / 1000.0))
                
                segment = {
                    "start": start_adj,
                    "end": end_adj,
                    "original_start": start_sec,
                    "original_end": end_sec
                }
                
                logger.debug(f"Adjusted segment {i}: {start_adj:.2f}s - {end_adj:.2f}s (original: {start_sec:.2f}s - {end_sec:.2f}s)")
                silent_segments.append(segment)
            
            return silent_segments
            
        except Exception as e:
            logger.error(f"Error detecting silent segments: {e}", exc_info=True)
            # Log the full traceback for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

# Register the processor
from app.editing.registry import register_processor

# Register the processor
register_processor('highlight_detector', HighlightDetector)
