from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BasicSegmenter:
    """
    A basic video segmenter that splits video into segments based on duration constraints.
    """
    
    def __init__(self, 
                 min_segment_duration: float = 2.0,
                 max_segment_duration: float = 15.0):
        """
        Initialize the segmenter with duration constraints.
        
        Args:
            min_segment_duration: Minimum duration of a segment in seconds
            max_segment_duration: Maximum duration of a segment in seconds
        """
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
    
    def segment(self, 
               video_duration: float,
               transcription: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Split the video into segments based on duration constraints.
        
        Args:
            video_duration: Total duration of the video in seconds
            transcription: Optional transcription data (not used in basic implementation)
            
        Returns:
            List of segment dictionaries with 'start' and 'end' times
        """
        segments = []
        current_time = 0.0
        
        while current_time < video_duration:
            segment_end = min(current_time + self.max_segment_duration, video_duration)
            
            # Ensure segment meets minimum duration requirement
            if segment_end - current_time >= self.min_segment_duration:
                segments.append({
                    'start': current_time,
                    'end': segment_end,
                    'text': '',
                    'speaker': ''
                })
            
            current_time = segment_end
        
        logger.info(f"Created {len(segments)} segments")
        return segments
