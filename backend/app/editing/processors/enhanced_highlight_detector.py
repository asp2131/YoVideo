"""
Enhanced Highlight Detector with OpusClip-level Quality

This implementation focuses on:
1. Multi-modal feature fusion
2. Advanced scoring algorithms
3. Better segment ranking
4. Content-aware selection
"""
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
import asyncio

from ..pipeline.core import VideoProcessor, Context, PipelineError, Segment, Progress, ProcessingStatus, CancellationToken
from ..analyzers import get_analyzer

logger = logging.getLogger(__name__)

@dataclass
class AdvancedSegmentFeatures:
    """Comprehensive features for a video segment."""
    # Basic features
    start: float
    end: float
    duration: float
    
    # Audio features
    audio_energy: float = 0.0
    audio_variance: float = 0.0
    spectral_centroid: float = 0.0
    zero_crossing_rate: float = 0.0
    mfcc_features: List[float] = None
    speech_probability: float = 0.0
    music_probability: float = 0.0
    
    # Visual features
    motion_intensity: float = 0.0
    scene_complexity: float = 0.0
    face_count: int = 0
    face_prominence: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    colorfulness: float = 0.0
    sharpness: float = 0.0
    
    # Content features
    word_count: int = 0
    speaking_rate: float = 0.0
    sentiment_polarity: float = 0.0
    sentiment_subjectivity: float = 0.0
    keyword_density: float = 0.0
    question_count: int = 0
    exclamation_count: int = 0
    caps_ratio: float = 0.0
    
    # Context features
    position_in_video: float = 0.0
    silence_ratio: float = 0.0
    scene_change_proximity: float = 0.0
    speaker_change: bool = False
    
    # Engagement indicators
    energy_peaks: int = 0
    topic_transition: bool = False
    emotional_intensity: float = 0.0
    
    def __post_init__(self):
        if self.mfcc_features is None:
            self.mfcc_features = []

@dataclass
class HighlightScore:
    """Detailed scoring breakdown for highlights."""
    audio_score: float = 0.0
    visual_score: float = 0.0
    content_score: float = 0.0
    engagement_score: float = 0.0
    context_score: float = 0.0
    diversity_bonus: float = 0.0
    total_score: float = 0.0
    
    # Sub-scores for interpretability
    energy_subscore: float = 0.0
    motion_subscore: float = 0.0
    speech_subscore: float = 0.0
    sentiment_subscore: float = 0.0
    face_subscore: float = 0.0

class OpusClipLevelHighlightDetector(VideoProcessor):
    """
    Advanced highlight detector that rivals OpusClip quality.
    
    Key improvements:
    1. Comprehensive multi-modal feature extraction
    2. Advanced scoring algorithms with sub-component analysis
    3. Content-aware segment selection
    4. Diversity optimization
    5. Context-sensitive weighting
    """
    
    def __init__(
        self,
        min_duration: float = 3.0,
        max_duration: float = 20.0,
        target_total_duration: float = 60.0,
        audio_weight: float = 0.25,
        visual_weight: float = 0.35,
        content_weight: float = 0.25,
        engagement_weight: float = 0.15,
        diversity_lambda: float = 0.3,
        quality_threshold: float = 0.4,
        max_highlights: int = 10
    ):
        """Initialize the advanced highlight detector."""
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_total_duration = target_total_duration
        self.audio_weight = audio_weight
        self.visual_weight = visual_weight
        self.content_weight = content_weight
        self.engagement_weight = engagement_weight
        self.diversity_lambda = diversity_lambda
        self.quality_threshold = quality_threshold
        self.max_highlights = max_highlights
        
        # Initialize analyzers
        self.analyzers = {}
        
    async def initialize_analyzers(self):
        """Initialize all analyzers."""
        try:
            self.analyzers['audio'] = get_analyzer('audio', sample_rate=16000)
            self.analyzers['visual'] = get_analyzer('visual', frame_rate=2.0)
            self.analyzers['content'] = get_analyzer('content')
            
            for analyzer in self.analyzers.values():
                await analyzer.initialize()
                
        except Exception as e:
            logger.warning(f"Some analyzers failed to initialize: {e}")
    
    async def cleanup_analyzers(self):
        """Cleanup analyzers."""
        for analyzer in self.analyzers.values():
            try:
                await analyzer.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up analyzer: {e}")
    
    def process(
        self,
        context: Context,
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """Process segments to detect high-quality highlights."""
        return asyncio.run(self._async_process(context, progress_callback, cancel_token))
    
    async def _async_process(
        self,
        context: Context,
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """Async implementation of the processing."""
        cancel_token = cancel_token or CancellationToken()
        
        try:
            # Initialize analyzers
            self._update_progress(progress_callback, 0, 6, ProcessingStatus.RUNNING, "Initializing analyzers")
            await self.initialize_analyzers()
            
            # Extract comprehensive features
            self._update_progress(progress_callback, 1, 6, ProcessingStatus.RUNNING, "Extracting features")
            cancel_token.check_cancelled()
            
            segments = getattr(context, 'segments', [])
            if not segments:
                logger.warning("No segments found for highlight detection")
                return context
            
            # Extract features for all segments
            segment_features = await self._extract_comprehensive_features(
                segments, context, cancel_token
            )
            
            # Score segments
            self._update_progress(progress_callback, 3, 6, ProcessingStatus.RUNNING, "Scoring segments")
            cancel_token.check_cancelled()
            
            scored_segments = self._score_segments_advanced(segment_features, context)
            
            # Select diverse highlights
            self._update_progress(progress_callback, 4, 6, ProcessingStatus.RUNNING, "Selecting highlights")
            cancel_token.check_cancelled()
            
            highlights = self._select_diverse_highlights(scored_segments, context)
            
            # Post-process and rank
            self._update_progress(progress_callback, 5, 6, ProcessingStatus.RUNNING, "Post-processing")
            final_highlights = self._post_process_highlights(highlights, context)
            
            # Store results
            context.highlights = final_highlights
            context.metadata['highlight_selection'] = {
                'total_candidates': len(segments),
                'scored_segments': len(scored_segments),
                'selected_highlights': len(final_highlights),
                'total_duration': sum(h.get('duration', 0) for h in final_highlights),
                'avg_score': np.mean([h.get('score', 0) for h in final_highlights]) if final_highlights else 0
            }
            
            self._update_progress(progress_callback, 6, 6, ProcessingStatus.COMPLETED, "Highlight detection complete")
            
            logger.info(f"Selected {len(final_highlights)} high-quality highlights")
            return context
            
        except Exception as e:
            error_msg = f"Advanced highlight detection failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PipelineError(error_msg) from e
        finally:
            await self.cleanup_analyzers()
    
    async def _extract_comprehensive_features(
        self, 
        segments: List[Segment], 
        context: Context,
        cancel_token: CancellationToken
    ) -> List[AdvancedSegmentFeatures]:
        """Extract comprehensive features for all segments."""
        features_list = []
        
        for i, segment in enumerate(segments):
            cancel_token.check_cancelled()
            
            features = AdvancedSegmentFeatures(
                start=segment.start,
                end=segment.end,
                duration=segment.end - segment.start,
                position_in_video=segment.start / getattr(context, 'duration', 1)
            )
            
            # Extract audio features
            if 'audio' in self.analyzers:
                await self._extract_audio_features(features, segment, context)
            
            # Extract visual features
            if 'visual' in self.analyzers:
                await self._extract_visual_features(features, segment, context)
            
            # Extract content features
            if 'content' in self.analyzers:
                await self._extract_content_features(features, segment, context)
            
            # Calculate context features
            self._calculate_context_features(features, segment, context, i, len(segments))
            
            features_list.append(features)
        
        return features_list
    
    async def _extract_audio_features(
        self, 
        features: AdvancedSegmentFeatures, 
        segment: Segment, 
        context: Context
    ):
        """Extract detailed audio features."""
        try:
            # Get audio analysis results from context or run analysis
            if hasattr(context, 'audio_analysis'):
                audio_data = context.audio_analysis
            else:
                # Run audio analysis on the segment
                analyzer = self.analyzers['audio']
                result = await analyzer.analyze(Path(context.video_path))
                audio_data = result.features
            
            # Extract time-specific features for this segment
            if 'rms_energy' in audio_data:
                features.audio_energy = float(audio_data['rms_energy'])
            
            if 'spectral_centroid' in audio_data:
                features.spectral_centroid = float(audio_data['spectral_centroid'])
            
            if 'zcr' in audio_data:
                features.zero_crossing_rate = float(audio_data['zcr'])
            
            # MFCC features
            mfcc_keys = [k for k in audio_data.keys() if k.startswith('mfcc_') and k.endswith('_mean')]
            features.mfcc_features = [audio_data[k] for k in mfcc_keys]
            
            # Speech/music classification
            if 'is_speech' in audio_data:
                features.speech_probability = float(audio_data['is_speech'])
                features.music_probability = 1.0 - features.speech_probability
            
            # Energy variance (excitement indicator)
            if hasattr(segment, 'audio_energy_variance'):
                features.audio_variance = segment.audio_energy_variance
            
        except Exception as e:
            logger.warning(f"Audio feature extraction failed: {e}")
    
    async def _extract_visual_features(
        self, 
        features: AdvancedSegmentFeatures, 
        segment: Segment, 
        context: Context
    ):
        """Extract detailed visual features."""
        try:
            # Get visual analysis results
            if hasattr(context, 'visual_analysis'):
                visual_data = context.visual_analysis
            else:
                analyzer = self.analyzers['visual']
                result = await analyzer.analyze(Path(context.video_path))
                visual_data = result.features
            
            # Motion intensity
            if 'motion_energy_mean' in visual_data:
                features.motion_intensity = float(visual_data['motion_energy_mean'])
            
            # Face detection
            if 'face_count_mean' in visual_data:
                features.face_count = int(visual_data['face_count_mean'])
                features.face_prominence = float(visual_data.get('face_count_max', 0))
            
            # Visual quality metrics
            features.brightness = float(visual_data.get('brightness_mean', 0.5))
            features.contrast = float(visual_data.get('contrast_mean', 0.5))
            features.colorfulness = float(visual_data.get('colorfulness_mean', 0.5))
            features.sharpness = float(visual_data.get('sharpness_mean', 0.5))
            
            # Scene complexity (based on edges, textures)
            if 'sharpness_std' in visual_data:
                features.scene_complexity = float(visual_data['sharpness_std'])
            
        except Exception as e:
            logger.warning(f"Visual feature extraction failed: {e}")
    
    async def _extract_content_features(
        self, 
        features: AdvancedSegmentFeatures, 
        segment: Segment, 
        context: Context
    ):
        """Extract detailed content features."""
        try:
            text = getattr(segment, 'text', '') or ''
            
            if not text:
                return
            
            # Basic text metrics
            words = text.split()
            features.word_count = len(words)
            features.speaking_rate = features.word_count / features.duration if features.duration > 0 else 0
            
            # Sentiment analysis
            if hasattr(context, 'content_analysis'):
                content_data = context.content_analysis
                features.sentiment_polarity = float(content_data.get('avg_polarity', 0))
                features.sentiment_subjectivity = float(content_data.get('avg_subjectivity', 0))
            
            # Engagement indicators
            features.question_count = text.count('?')
            features.exclamation_count = text.count('!')
            
            # Caps ratio (intensity indicator)
            caps_words = sum(1 for word in words if word.isupper() and len(word) > 1)
            features.caps_ratio = caps_words / len(words) if words else 0
            
            # Keyword density (topic relevance)
            engagement_keywords = [
                'amazing', 'incredible', 'wow', 'awesome', 'fantastic', 'unbelievable',
                'important', 'crucial', 'essential', 'key', 'significant',
                'first', 'finally', 'conclusion', 'summary', 'result'
            ]
            
            keyword_count = sum(1 for word in words if word.lower() in engagement_keywords)
            features.keyword_density = keyword_count / len(words) if words else 0
            
            # Emotional intensity
            features.emotional_intensity = (
                abs(features.sentiment_polarity) + 
                features.sentiment_subjectivity +
                features.caps_ratio +
                (features.question_count + features.exclamation_count) / max(1, len(words)) * 10
            ) / 4
            
        except Exception as e:
            logger.warning(f"Content feature extraction failed: {e}")
    
    def _calculate_context_features(
        self, 
        features: AdvancedSegmentFeatures, 
        segment: Segment, 
        context: Context,
        segment_index: int,
        total_segments: int
    ):
        """Calculate context-dependent features."""
        # Silence ratio
        if hasattr(context, 'silence_sections'):
            silence_duration = 0
            for silence in context.silence_sections:
                overlap_start = max(features.start, silence.get('start', 0))
                overlap_end = min(features.end, silence.get('end', 0))
                if overlap_end > overlap_start:
                    silence_duration += overlap_end - overlap_start
            features.silence_ratio = silence_duration / features.duration
        
        # Scene change proximity
        if hasattr(context, 'scene_changes'):
            min_distance = float('inf')
            for scene_time in context.scene_changes:
                distance = min(abs(features.start - scene_time), abs(features.end - scene_time))
                min_distance = min(min_distance, distance)
            features.scene_change_proximity = 1.0 / (1.0 + min_distance) if min_distance != float('inf') else 0
        
        # Energy peaks in audio
        if hasattr(segment, 'energy_peaks'):
            features.energy_peaks = len(segment.energy_peaks)
    
    def _score_segments_advanced(
        self, 
        segment_features: List[AdvancedSegmentFeatures], 
        context: Context
    ) -> List[Tuple[AdvancedSegmentFeatures, HighlightScore]]:
        """Advanced scoring algorithm with multiple components."""
        scored_segments = []
        
        # Normalize features across all segments for relative scoring
        feature_stats = self._calculate_feature_statistics(segment_features)
        
        for features in segment_features:
            score = HighlightScore()
            
            # Audio scoring
            score.audio_score = self._score_audio_features(features, feature_stats)
            score.energy_subscore = self._normalize_feature(features.audio_energy, feature_stats['audio_energy'])
            
            # Visual scoring
            score.visual_score = self._score_visual_features(features, feature_stats)
            score.motion_subscore = self._normalize_feature(features.motion_intensity, feature_stats['motion_intensity'])
            score.face_subscore = self._normalize_feature(features.face_prominence, feature_stats['face_prominence'])
            
            # Content scoring
            score.content_score = self._score_content_features(features, feature_stats)
            score.speech_subscore = self._normalize_feature(features.speaking_rate, feature_stats['speaking_rate'])
            score.sentiment_subscore = abs(features.sentiment_polarity) * features.sentiment_subjectivity
            
            # Engagement scoring
            score.engagement_score = self._score_engagement_features(features, feature_stats)
            
            # Context scoring
            score.context_score = self._score_context_features(features, context)
            
            # Calculate total score
            score.total_score = (
                score.audio_score * self.audio_weight +
                score.visual_score * self.visual_weight +
                score.content_score * self.content_weight +
                score.engagement_score * self.engagement_weight
            ) * (1.0 + score.context_score * 0.2)  # Context as a multiplier
            
            scored_segments.append((features, score))
        
        # Sort by total score
        scored_segments.sort(key=lambda x: x[1].total_score, reverse=True)
        
        return scored_segments
    
    def _calculate_feature_statistics(self, features_list: List[AdvancedSegmentFeatures]) -> Dict[str, Dict[str, float]]:
        """Calculate statistics for feature normalization."""
        stats = {}
        
        # Define features to normalize
        numeric_features = [
            'audio_energy', 'spectral_centroid', 'zero_crossing_rate',
            'motion_intensity', 'face_prominence', 'brightness', 'contrast',
            'word_count', 'speaking_rate', 'emotional_intensity'
        ]
        
        for feature_name in numeric_features:
            values = [getattr(f, feature_name, 0) for f in features_list]
            stats[feature_name] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'median': np.median(values)
            }
        
        return stats
    
    def _normalize_feature(self, value: float, stats: Dict[str, float]) -> float:
        """Normalize a feature value using z-score with clipping."""
        if stats['std'] == 0:
            return 0.5
        
        z_score = (value - stats['mean']) / stats['std']
        # Convert to 0-1 range, clipping at ±2 standard deviations
        normalized = (np.clip(z_score, -2, 2) + 2) / 4
        return float(normalized)
    
    def _score_audio_features(self, features: AdvancedSegmentFeatures, stats: Dict) -> float:
        """Score audio features with sophisticated weighting."""
        # Energy scoring (moderate energy is good, too high/low is bad)
        energy_norm = self._normalize_feature(features.audio_energy, stats['audio_energy'])
        energy_score = 1.0 - abs(energy_norm - 0.7) * 2  # Peak at 70th percentile
        
        # Spectral centroid (speech clarity)
        spectral_score = self._normalize_feature(features.spectral_centroid, stats['spectral_centroid'])
        
        # Speech probability bonus
        speech_bonus = features.speech_probability * 0.3
        
        # Combine with weights
        audio_score = (
            energy_score * 0.4 +
            spectral_score * 0.3 +
            features.speech_probability * 0.3
        ) + speech_bonus
        
        return max(0, min(1, audio_score))
    
    def _score_visual_features(self, features: AdvancedSegmentFeatures, stats: Dict) -> float:
        """Score visual features focusing on engagement indicators."""
        # Motion scoring (moderate motion is engaging)
        motion_norm = self._normalize_feature(features.motion_intensity, stats['motion_intensity'])
        motion_score = 1.0 - abs(motion_norm - 0.6) * 1.5  # Peak at 60th percentile
        
        # Face presence bonus
        face_score = min(1.0, features.face_count * 0.3 + features.face_prominence * 0.2)
        
        # Visual quality (contrast and sharpness)
        quality_score = (features.contrast + features.sharpness) / 2
        
        # Combine
        visual_score = (
            max(0, motion_score) * 0.4 +
            face_score * 0.35 +
            quality_score * 0.25
        )
        
        return max(0, min(1, visual_score))
    
    def _score_content_features(self, features: AdvancedSegmentFeatures, stats: Dict) -> float:
        """Score content features for engagement and informativeness."""
        # Speaking rate (moderate rate is best)
        rate_norm = self._normalize_feature(features.speaking_rate, stats['speaking_rate'])
        rate_score = 1.0 - abs(rate_norm - 0.6) * 1.2  # Optimal around 60th percentile
        
        # Emotional content
        emotion_score = min(1.0, features.emotional_intensity * 0.8)
        
        # Keyword density
        keyword_score = min(1.0, features.keyword_density * 2.0)
        
        # Question/exclamation bonus
        engagement_bonus = min(0.3, (features.question_count + features.exclamation_count) * 0.1)
        
        content_score = (
            max(0, rate_score) * 0.3 +
            emotion_score * 0.3 +
            keyword_score * 0.2 +
            abs(features.sentiment_polarity) * features.sentiment_subjectivity * 0.2
        ) + engagement_bonus
        
        return max(0, min(1, content_score))
    
    def _score_engagement_features(self, features: AdvancedSegmentFeatures, stats: Dict) -> float:
        """Score overall engagement potential."""
        engagement_score = (
            features.emotional_intensity * 0.3 +
            min(1.0, features.energy_peaks * 0.1) * 0.2 +
            features.keyword_density * 0.2 +
            (1.0 - features.silence_ratio) * 0.3
        )
        
        return max(0, min(1, engagement_score))
    
    def _score_context_features(self, features: AdvancedSegmentFeatures, context: Context) -> float:
        """Score context-dependent features."""
        context_score = 0.0
        
        # Position in video (beginning and end get slight bonus)
        position_bonus = 0.1 if features.position_in_video < 0.1 or features.position_in_video > 0.9 else 0.0
        
        # Scene change proximity bonus
        scene_bonus = features.scene_change_proximity * 0.2
        
        # Speaker change bonus
        speaker_bonus = 0.1 if features.speaker_change else 0.0
        
        context_score = position_bonus + scene_bonus + speaker_bonus
        
        return max(0, min(0.5, context_score))  # Cap context bonus
    
    def _select_diverse_highlights(
        self, 
        scored_segments: List[Tuple[AdvancedSegmentFeatures, HighlightScore]], 
        context: Context
    ) -> List[Dict[str, Any]]:
        """Select diverse highlights using advanced selection algorithm."""
        if not scored_segments:
            return []
        
        # Filter by quality threshold
        quality_segments = [
            (features, score) for features, score in scored_segments
            if score.total_score >= self.quality_threshold
        ]
        
        if not quality_segments:
            # If no segments meet threshold, take top 20% anyway
            threshold_index = max(1, len(scored_segments) // 5)
            quality_segments = scored_segments[:threshold_index]
        
        # Apply diversity selection
        selected = []
        total_duration = 0.0
        
        # Feature vectors for diversity calculation
        feature_vectors = []
        for features, score in quality_segments:
            vector = np.array([
                features.audio_energy,
                features.motion_intensity,
                features.speaking_rate,
                features.emotional_intensity,
                features.position_in_video,
                score.total_score
            ])
            feature_vectors.append(vector)
        
        feature_vectors = np.array(feature_vectors)
        if len(feature_vectors) > 0:
            # Normalize feature vectors
            feature_vectors = (feature_vectors - feature_vectors.mean(axis=0)) / (feature_vectors.std(axis=0) + 1e-8)
        
        selected_indices = set()
        
        # Greedy selection with diversity
        while (len(selected) < self.max_highlights and 
               total_duration < self.target_total_duration and 
               len(selected_indices) < len(quality_segments)):
            
            best_score = -1
            best_idx = -1
            
            for i, (features, score) in enumerate(quality_segments):
                if i in selected_indices:
                    continue
                
                # Check duration constraint
                if total_duration + features.duration > self.target_total_duration and selected:
                    continue
                
                # Calculate diversity penalty
                diversity_penalty = 0.0
                if selected_indices and len(feature_vectors) > i:
                    selected_vectors = feature_vectors[list(selected_indices)]
                    current_vector = feature_vectors[i]
                    
                    # Calculate minimum distance to selected segments
                    distances = np.linalg.norm(selected_vectors - current_vector, axis=1)
                    diversity_penalty = np.exp(-np.min(distances)) * self.diversity_lambda
                
                # Combined score
                combined_score = score.total_score * (1.0 - diversity_penalty)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_idx = i
            
            if best_idx == -1:
                break
            
            features, score = quality_segments[best_idx]
            selected_indices.add(best_idx)
            total_duration += features.duration
            
            highlight = {
                'start': features.start,
                'end': features.end,
                'duration': features.duration,
                'score': score.total_score,
                'score_breakdown': {
                    'audio': score.audio_score,
                    'visual': score.visual_score,
                    'content': score.content_score,
                    'engagement': score.engagement_score,
                    'context': score.context_score
                },
                'features': {
                    'audio_energy': features.audio_energy,
                    'motion_intensity': features.motion_intensity,
                    'face_count': features.face_count,
                    'speaking_rate': features.speaking_rate,
                    'emotional_intensity': features.emotional_intensity,
                    'word_count': features.word_count
                }
            }
            selected.append(highlight)
        
        return selected
    
    def _post_process_highlights(self, highlights: List[Dict[str, Any]], context: Context) -> List[Dict[str, Any]]:
        """Final post-processing of selected highlights."""
        if not highlights:
            return highlights
        
        # Sort by start time
        highlights.sort(key=lambda x: x['start'])
        
        # Add metadata
        for i, highlight in enumerate(highlights):
            highlight['index'] = i
            highlight['rank'] = i + 1
            
            # Add text if available
            text_segments = []
            if hasattr(context, 'transcription'):
                for seg in context.transcription:
                    if (seg.get('start', 0) >= highlight['start'] and 
                        seg.get('end', 0) <= highlight['end']):
                        text_segments.append(seg.get('text', ''))
            
            highlight['text'] = ' '.join(text_segments)
        
        return highlights
    
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
                metadata={'processor': 'OpusClipLevelHighlightDetector'}
            )
            progress_callback(progress)