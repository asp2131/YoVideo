from typing import Optional, List, Dict, Any, Callable
import logging
from ..pipeline.core import VideoProcessor, Context, PipelineError, Progress, ProcessingStatus, CancellationToken

logger = logging.getLogger(__name__)

class BasicSegmenter(VideoProcessor):
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
    
    def process(self, 
                context: Context, 
                progress_callback: Optional[Callable[[Progress], None]] = None,
                cancel_token: Optional[CancellationToken] = None) -> Context:
        """
        Process the context to create segments based on duration constraints.
        
        Args:
            context: The processing context
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with segments
        """
        cancel_token = cancel_token or CancellationToken()
        
        try:
            # Update progress
            if progress_callback:
                progress_callback(Progress(
                    current=0, total=2, status=ProcessingStatus.RUNNING,
                    message="Starting basic segmentation"
                ))
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Get video duration from context
            video_duration = getattr(context, 'duration', 0)
            if video_duration <= 0:
                # Try to get duration from metadata
                video_duration = context.metadata.get('duration', 0)
                if video_duration <= 0:
                    logger.warning("No video duration available for segmentation")
                    video_duration = 60.0  # Default to 60 seconds
            
            # Get transcription if available
            transcription = getattr(context, 'transcription', None)
            
            # Create segments
            segments = self.segment(video_duration, transcription)
            
            # Convert to Segment objects and store in context
            from ..pipeline.core import Segment
            context.segments = []
            
            for seg_dict in segments:
                segment = Segment(
                    start=seg_dict['start'],
                    end=seg_dict['end'],
                    text=seg_dict.get('text', ''),
                    speaker=seg_dict.get('speaker', '')
                )
                context.segments.append(segment)
            
            # Update progress
            if progress_callback:
                progress_callback(Progress(
                    current=2, total=2, status=ProcessingStatus.COMPLETED,
                    message=f"Created {len(context.segments)} segments"
                ))
            
            logger.info(f"Created {len(context.segments)} segments")
            return context
            
        except Exception as e:
            error_msg = f"Basic segmentation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if progress_callback:
                progress_callback(Progress(
                    status=ProcessingStatus.FAILED,
                    message=error_msg
                ))
            
            raise PipelineError(error_msg) from e
    
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