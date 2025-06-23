"""
Enhanced Highlight Detector

A multi-modal processor that identifies highlight-worthy segments in videos
using a combination of audio, visual, and content analysis.
"""
import logging
from typing import Dict, List, Any, cast
from dataclasses import dataclass
from typing import Optional

from ..pipeline.core import VideoProcessor, Context, PipelineError, Segment

logger = logging.getLogger(__name__)

@dataclass
class HighlightScore:
    """Scores for different aspects of a highlight segment."""
    audio: float = 0.0
    visual: float = 0.0
    content: float = 0.0
    scene_change: float = 0.0
    silence_penalty: float = 0.0
    
    @property
    def total(self) -> float:
        return self.audio + self.visual + self.content + self.scene_change - self.silence_penalty

class EnhancedHighlightDetector(VideoProcessor):
    """
    Enhanced highlight detector that uses multi-modal analysis to identify
    the most engaging segments of a video.
    
    This processor analyzes segments from the context and assigns highlight
    scores based on audio, visual, and content features. It selects the top
    segments up to a target duration and stores them in the context.
    """
    
    def __init__(
        self,
        min_duration: float = 2.0,
        max_duration: float = 15.0,
        target_total_duration: float = 60.0,
        audio_weight: float = 0.4,
        visual_weight: float = 0.3,
        content_weight: float = 0.3,
        scene_change_bonus: float = 0.2,
        silence_penalty: float = 0.3,
        face_detection_enabled: bool = True,
        motion_analysis_enabled: bool = True,
        sentiment_analysis_enabled: bool = True
    ):
        """
        Initialize the enhanced highlight detector.
        
        Args:
            min_duration: Minimum duration of a highlight segment (seconds)
            max_duration: Maximum duration of a highlight segment (seconds)
            target_total_duration: Target total duration of all highlights (seconds)
            audio_weight: Weight for audio features in scoring (0-1)
            visual_weight: Weight for visual features in scoring (0-1)
            content_weight: Weight for content features in scoring (0-1)
            scene_change_bonus: Bonus score for segments near scene changes
            silence_penalty: Penalty for segments with high silence ratio
            face_detection_enabled: Whether to perform face detection
            motion_analysis_enabled: Whether to analyze motion
            sentiment_analysis_enabled: Whether to analyze sentiment in text
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_total_duration = target_total_duration
        self.scene_change_bonus = scene_change_bonus
        self.silence_penalty = silence_penalty
        self.face_detection_enabled = face_detection_enabled
        self.motion_analysis_enabled = motion_analysis_enabled
        self.sentiment_analysis_enabled = sentiment_analysis_enabled
        
        # Normalize weights to sum to 1
        total = audio_weight + visual_weight + content_weight
        if total > 0:
            self.audio_weight = audio_weight / total
            self.visual_weight = visual_weight / total
            self.content_weight = content_weight / total
        else:
            self.audio_weight = 0.33
            self.visual_weight = 0.33
            self.content_weight = 0.34
    
    def process(self, context: Context) -> Context:
        """
        Process segments to detect highlights.
        
        Args:
            context: The processing context containing segments and features
            
        Returns:
            Updated context with highlight segments
            
        Raises:
            PipelineError: If highlight detection fails
        """
        try:
            logger.info("Starting enhanced highlight detection")
            
            if not hasattr(context, 'segments') or not context.segments:
                logger.warning("No segments found in context, skipping highlight detection")
                return context
            
            # Score each segment
            scored_segments = []
            for i, segment in enumerate(context.segments):
                score = self._score_segment(segment, context, i, len(context.segments))
                scored_segments.append((segment, score))
            
            # Sort by total score (descending)
            scored_segments.sort(key=lambda x: x[1].total, reverse=True)
            
            # Select top segments up to target duration
            selected_segments = []
            total_duration = 0.0
            
            for segment, score in scored_segments:
                segment_duration = segment.end - segment.start
                
                # Skip segments that are too short or too long
                if segment_duration < self.min_duration or segment_duration > self.max_duration:
                    continue
                    
                # Check if adding this segment would exceed target duration
                if total_duration + segment_duration > self.target_total_duration and total_duration > 0:
                    break
                    
                # Add segment to highlights
                selected_segments.append({
                    'start': segment.start,
                    'end': segment.end,
                    'score': score.total,
                    'score_details': {
                        'audio': score.audio,
                        'visual': score.visual,
                        'content': score.content,
                        'scene_change': score.scene_change,
                        'silence_penalty': score.silence_penalty
                    },
                    'text': getattr(segment, 'text', ''),
                    'speaker': getattr(segment, 'speaker', None)
                })
                total_duration += segment_duration
            
            # Store results in context
            context.highlights = selected_segments
            context.metadata['highlight_selection'] = {
                'total_duration': total_duration,
                'segment_count': len(selected_segments),
                'target_duration': min(self.target_total_duration, total_duration)
            }
            
            logger.info(f"Selected {len(selected_segments)} highlight segments "
                      f"(total duration: {total_duration:.1f}s)")
            
            return context
            
        except Exception as e:
            raise PipelineError(f"Highlight detection failed: {str(e)}") from e
    
    def _score_segment(self, segment: Segment, context: Context, 
                      segment_idx: int = 0, total_segments: int = 1) -> HighlightScore:
        """
        Score a segment based on various features.
        
        Args:
            segment: The segment to score
            context: Processing context
            segment_idx: Index of the current segment
            total_segments: Total number of segments
            
        Returns:
            HighlightScore object with component scores
        """
        score = HighlightScore()
        
        # Audio features
        if hasattr(segment, 'audio_energy'):
            score.audio = self._normalize(segment.audio_energy) * self.audio_weight
        
        # Visual features
        if hasattr(segment, 'visual_activity'):
            score.visual = self._normalize(segment.visual_activity) * self.visual_weight
        
        # Content features
        if hasattr(segment, 'text') and segment.text:
            # Simple heuristic: longer text is better
            score.content = self._normalize(len(segment.text)) * self.content_weight
        
        # Scene change bonus
        if hasattr(segment, 'scene_change') and segment.scene_change:
            score.scene_change = self.scene_change_bonus
        
        # Silence penalty
        if hasattr(segment, 'silence_ratio'):
            score.silence_penalty = segment.silence_ratio * self.silence_penalty
        
        return score
    
    def _normalize(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Normalize a value to 0-1 range."""
        if max_val <= min_val:
            return 0.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    def _create_default_segments(self, context: Context) -> List[Segment]:
        """
        Create default segments if none are provided.
        
        This is a fallback that creates segments of equal duration.
        
        Args:
            context: The processing context
            
        Returns:
            List of created segments
        """
        if not hasattr(context, 'duration') or context.duration <= 0:
            return []
            
        segment_count = max(1, int(context.duration / self.max_duration))
        segment_duration = context.duration / segment_count
        
        segments = []
        for i in range(segment_count):
            start = i * segment_duration
            end = start + segment_duration if i < segment_count - 1 else context.duration
            segments.append(Segment(start=start, end=end))
            
        return segments
    
    def _analyze_audio(self, segment: Segment, audio_features: Dict[str, Any]) -> float:
        """
        Analyze audio features for the segment.
        
        Args:
            segment: The segment to analyze
            audio_features: Dictionary of audio features
            
        Returns:
            Audio analysis score between 0 and 1
        """
        return 0.5  # Placeholder implementation
    
    def _analyze_visual(self, segment: Segment, visual_features: Dict[str, Any]) -> float:
        """
        Analyze visual features for the segment.
        
        Args:
            segment: The segment to analyze
            visual_features: Dictionary of visual features
            
        Returns:
            Visual analysis score between 0 and 1
        """
        return 0.5  # Placeholder implementation
    
    def _analyze_content(self, segment: Segment, transcription: List[Dict[str, Any]]) -> float:
        """
        Analyze content features for the segment.
        
        Args:
            segment: The segment to analyze
            transcription: List of transcription segments
            
        Returns:
            Content analysis score between 0 and 1
        """
        return 0.5  # Placeholder implementation
