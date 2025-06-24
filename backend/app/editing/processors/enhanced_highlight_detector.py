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
                    
                # Add segment to highlights with annotations
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
                    'speaker': getattr(segment, 'speaker', None),
                    'annotations': {
                        'scene_change': getattr(segment, 'scene_change', False),
                        'silence_ratio': getattr(segment, 'silence_ratio', 0.0),
                        'is_silent': getattr(segment, 'is_silent', False),
                        'scene_boundary': getattr(segment, 'scene_boundary', False)
                    }
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
        # Initialize with default weights if not set
        if not hasattr(self, 'audio_weight'):
            self.audio_weight = 0.4
            self.visual_weight = 0.3
            self.content_weight = 0.3
            
        # Calculate position-based scoring
        position_ratio = segment_idx / max(1, total_segments - 1)
        position_score = 1.0 - abs(0.5 - position_ratio) * 1.5  # Peak at middle
        """
        Score a segment based on various features including scene changes, silence, and audio features.
        
        Args:
            segment: The segment to score
            context: Processing context with scene changes and silence info
            segment_idx: Index of the current segment
            total_segments: Total number of segments
            
        Returns:
            HighlightScore object with component scores
        """
        score = HighlightScore()
        
        # Initialize annotations if not present
        if not hasattr(segment, 'annotations'):
            segment.annotations = {}
        
        # Check for scene changes at segment boundaries
        if hasattr(context, 'scene_changes'):
            # Check if this segment starts or ends at a scene boundary
            scene_boundary = any(
                abs(segment.start - scene_time) < 0.5 or 
                abs(segment.end - scene_time) < 0.5
                for scene_time in context.scene_changes
            )
            segment.scene_boundary = scene_boundary
            segment.annotations['scene_boundary'] = scene_boundary
            
            # Check if this segment contains a scene change
            if hasattr(segment, 'scene_change') and segment.scene_change:
                score.scene_change = self.scene_change_bonus
                segment.annotations['scene_change'] = True
        
        # Process silence information
        if hasattr(context, 'silence_segments'):
            # Calculate silence ratio for this segment
            silence_duration = 0.0
            for silence_start, silence_end in context.silence_segments:
                # Calculate overlap between silence and segment
                overlap_start = max(segment.start, silence_start)
                overlap_end = min(segment.end, silence_end)
                if overlap_start < overlap_end:
                    silence_duration += (overlap_end - overlap_start)
            
            segment_duration = segment.end - segment.start
            silence_ratio = silence_duration / segment_duration if segment_duration > 0 else 0.0
            segment.silence_ratio = silence_ratio
            segment.is_silent = silence_ratio > 0.5  # Consider segment silent if >50% is silence
            
            segment.annotations.update({
                'silence_ratio': silence_ratio,
                'is_silent': segment.is_silent
            })
            
            # Apply silence penalty
            if silence_ratio > 0.1:  # Only apply penalty for significant silence
                score.silence_penalty = silence_ratio * self.silence_penalty
        
        # Audio features scoring
        audio_score = 0.0
        audio_features = {}
        
        # Energy-based scoring
        if hasattr(segment, 'energy_ratio'):
            # Higher energy is generally better, but not too high (avoid distortion)
            energy_score = min(1.0, segment.energy_ratio * 1.2)  # Cap at 1.2x average energy
            audio_features['energy'] = energy_score
            audio_score += energy_score * 0.4  # 40% weight to energy
        
        # Spectral centroid (brightness of sound)
        if hasattr(segment, 'spectral_centroid_mean'):
            # Higher spectral centroid indicates brighter sounds (speech, music)
            # Normalize to 0-1 range (assuming typical speech range 100-4000 Hz)
            centroid_score = min(1.0, max(0.0, (segment.spectral_centroid_mean - 100) / 3900))
            audio_features['spectral_centroid'] = centroid_score
            audio_score += centroid_score * 0.3  # 30% weight to spectral centroid
        
        # Zero crossing rate (noise vs tonal sounds)
        if hasattr(segment, 'zcr_mean'):
            # Moderate ZCR is good (too high = noise, too low = silence)
            zcr_score = 1.0 - abs(0.1 - min(0.2, segment.zcr_mean)) * 5  # Peak around 0.1
            audio_features['zcr'] = zcr_score
            audio_score += zcr_score * 0.2  # 20% weight to ZCR
        
        # Spectral bandwidth (complexity of sound)
        if hasattr(segment, 'spectral_bandwidth_mean'):
            # Moderate bandwidth is good (too high = noise, too low = simple tones)
            bandwidth_score = min(1.0, segment.spectral_bandwidth_mean / 2000)  # Normalize
            audio_features['bandwidth'] = bandwidth_score
            audio_score += bandwidth_score * 0.1  # 10% weight to bandwidth
        
        # Normalize audio score to 0-1 range
        audio_score = min(1.0, max(0.0, audio_score))
        
        # Apply silence penalty
        score.audio = audio_score * self.audio_weight
        
        # Visual features analysis
        visual_score = 0.3  # Default score if no visual features
        if hasattr(segment, 'visual_features'):
            visual_score = self._analyze_visual(segment, segment.visual_features)
        score.visual = visual_score * self.visual_weight
        
        # Content analysis
        content_score = 0.3  # Default score if no content features
        if hasattr(context, 'transcription'):
            content_score = self._analyze_content(segment, context.transcription)
        if hasattr(segment, 'text') and segment.text:
            # Simple heuristic: longer text is better, but penalize silent segments
            content_score = self._normalize(len(segment.text))
            if getattr(segment, 'is_silent', False):
                content_score *= 0.7  # 30% penalty for silent segments
        score.content = content_score * self.content_weight
        
        # Store feature scores in segment annotations for debugging
        segment.annotations.update({
            'audio_score': score.audio,
            'visual_score': score.visual,
            'content_score': score.content,
            'scene_change_bonus': score.scene_change,
            'silence_penalty': score.silence_penalty,
            'audio_features': audio_features,
            'position_ratio': position_ratio,
            'position_score': position_score,
            'segment_idx': segment_idx,
            'total_segments': total_segments
        })
        
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
        Analyze audio features for the segment to determine engagement potential.
        
        Args:
            segment: The segment to analyze
            audio_features: Dictionary of audio features with keys like 'energy', 'pitch', 'speech_probability'
            
        Returns:
            Audio analysis score between 0 and 1, where 1 is most engaging
        """
        if not audio_features:
            return 0.3  # Default score if no features available
            
        score = 0.0
        
        # Energy (loudness) - higher is better, but not too high
        energy = audio_features.get('energy', 0.5)
        energy_score = min(1.0, energy * 1.5)  # Cap at 1.5x average energy
        
        # Pitch variation - more variation is more engaging
        pitch_var = audio_features.get('pitch_variance', 0.0)
        pitch_score = min(1.0, pitch_var * 2.0)
        
        # Speech probability - prefer segments with clear speech
        speech_prob = audio_features.get('speech_probability', 0.0)
        
        # Combine features with weights
        score = (
            0.5 * energy_score +
            0.3 * pitch_score +
            0.2 * speech_prob
        )
        
        # Apply silence penalty if applicable
        if getattr(segment, 'is_silent', False):
            score *= 0.4  # 60% penalty for silent segments
            
        return min(1.0, max(0.0, score))  # Ensure 0-1 range
    
    def _analyze_visual(self, segment: Segment, visual_features: Dict[str, Any]) -> float:
        """
        Analyze visual features to determine engagement potential.
        
        Args:
            segment: The segment to analyze
            visual_features: Dictionary with keys like 'motion', 'contrast', 'face_detected'
            
        Returns:
            Visual analysis score between 0 and 1, where 1 is most engaging
        """
        if not visual_features:
            return 0.3  # Default score if no features available
            
        score = 0.0
        
        # Motion - moderate motion is most engaging
        motion = visual_features.get('motion', 0.5)
        motion_score = 1.0 - abs(0.6 - motion) * 2  # Peak at 0.6 motion
        
        # Face detection - prefer segments with faces
        face_score = 1.0 if visual_features.get('face_detected', False) else 0.3
        
        # Contrast - higher contrast is generally more engaging
        contrast = visual_features.get('contrast', 0.5)
        contrast_score = min(1.0, contrast * 1.5)
        
        # Combine features with weights
        score = (
            0.4 * motion_score +
            0.4 * face_score +
            0.2 * contrast_score
        )
        
        # Boost score for scene boundaries
        if getattr(segment, 'scene_boundary', False):
            score = min(1.0, score * 1.3)  # 30% boost for scene boundaries
            
        return min(1.0, max(0.0, score))  # Ensure 0-1 range
    
    def _analyze_content(self, segment: Segment, transcription: List[Dict[str, Any]]) -> float:
        """
        Analyze content features to determine engagement potential.
        
        Args:
            segment: The segment to analyze
            transcription: List of transcription segments with 'text', 'start', 'end', 'confidence'
            
        Returns:
            Content analysis score between 0 and 1, where 1 is most engaging
        """
        if not transcription:
            return 0.3  # Default score if no transcription
            
        # Find transcription segments that overlap with this video segment
        relevant_segments = [
            t for t in transcription 
            if t['end'] >= segment.start and t['start'] <= segment.end
        ]
        
        if not relevant_segments:
            return 0.2  # No relevant transcription
            
        # Calculate content metrics
        total_chars = sum(len(t.get('text', '')) for t in relevant_segments)
        avg_confidence = sum(t.get('confidence', 0.5) for t in relevant_segments) / len(relevant_segments)
        
        # Text features
        text = ' '.join(t.get('text', '') for t in relevant_segments)
        text_length = len(text)
        
        # Simple heuristic: prefer segments with moderate text length
        # (not too short, not too long)
        if text_length < 20:  # Very short text
            length_score = 0.3
        elif text_length > 200:  # Very long text
            length_score = 0.7
        else:  # Ideal length
            length_score = 1.0
            
        # Confidence score
        confidence_score = avg_confidence
        
        # Combine scores
        score = 0.6 * length_score + 0.4 * confidence_score
        
        # Apply penalties
        if getattr(segment, 'is_silent', False):
            score *= 0.7  # 30% penalty for silent segments
            
        return min(1.0, max(0.0, score))  # Ensure 0-1 range
