"""
Intelligent Content-Aware Segmentation System

This module provides advanced segmentation that understands video content structure
and creates natural segments based on topics, speakers, and content flow.
"""
import logging
import re
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field

# Optional imports with graceful fallback
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import networkx as nx
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning(
        "scikit-learn or networkx not available. "
        "Some features of IntelligentSegmenter will be limited."
    )

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    logging.warning(
        "TextBlob not available. "
        "Sentiment analysis features will be disabled."
    )

from ..pipeline.core import VideoProcessor, Context, PipelineError, Segment, Progress, ProcessingStatus, CancellationToken

logger = logging.getLogger(__name__)

# Regex for detecting sentence boundaries
SENTENCE_END = re.compile(r'[.!?]\s*$')

# Type aliases for better code readability
SegmentDict = Dict[str, Any]
Transcription = List[Dict[str, Any]]

@dataclass
class SegmentFeatures:
    """Features extracted for a video segment."""
    start_time: float
    end_time: float
    text: str = ""
    speaker: Optional[str] = None
    sentiment: Optional[float] = None
    tfidf_vector: Optional[Any] = None
    audio_energy: Optional[float] = None
    visual_activity: Optional[float] = None
    is_sentence_end: bool = False
    pause_after: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def is_valid(self) -> bool:
        return self.end_time > self.start_time and bool(self.text.strip())

class IntelligentSegmenter(VideoProcessor):
    """Advanced segmentation system that creates natural content boundaries
    based on semantic analysis, speaker changes, and topic shifts.
    
    This segmenter analyzes multiple aspects of video content to create
    meaningful segments that respect topic boundaries, speaker changes,
    and natural pauses in the content.
    
    This implementation works with the VideoProcessor pipeline and integrates
    with the shared Context object to access scene changes and silence information.
    """
    
    def __init__(
        self,
        min_segment_duration: float = 5.0,
        max_segment_duration: float = 30.0,
        semantic_threshold: float = 0.3,
        speaker_change_weight: float = 0.4,
        topic_change_weight: float = 0.6,
        use_scene_boundaries: bool = True,
        respect_silence: bool = True,
        pause_threshold: float = 1.0,
        min_silence_len: float = 0.8
    ):
        """
        Initialize the intelligent segmenter.
        
        Args:
            min_segment_duration: Minimum duration for a segment in seconds
            max_segment_duration: Maximum duration for a segment in seconds
            semantic_threshold: Threshold for semantic similarity (0-1)
            speaker_change_weight: Weight for speaker change detection (0-1)
            topic_change_weight: Weight for topic change detection (0-1)
            use_scene_boundaries: Whether to respect scene boundaries from SceneDetector
            respect_silence: Whether to avoid cutting in the middle of speech
            pause_threshold: Pause duration in seconds to consider as a boundary
            min_silence_len: Minimum silence length to consider for segmentation
        """
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.semantic_threshold = semantic_threshold
        self.speaker_change_weight = speaker_change_weight
        self.topic_change_weight = topic_change_weight
        self.use_scene_boundaries = use_scene_boundaries
        self.respect_silence = respect_silence
        self.pause_threshold = pause_threshold
        self.min_silence_len = min_silence_len
        
        if SKLEARN_AVAILABLE:
            # Initialize TF-IDF vectorizer for semantic analysis
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2),
                min_df=1
            )
    
    @property
    def name(self) -> str:
        return "intelligent_segmenter"
    
    def process(
        self,
        context: Context,
        progress_callback: Optional[Callable[[Progress], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Context:
        """
        Process the video context to create intelligent segments.
        
        Args:
            context: The processing context containing video path and other state
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with segments
            
        Raises:
            PipelineError: If segmentation fails
        """
        # Initialize cancellation
        cancel_token = cancel_token or CancellationToken()
        
        try:
            # Update progress
            self._update_progress(progress_callback, 0, 4, ProcessingStatus.RUNNING, "Starting segmentation")
            
            # Get transcription from context
            transcription = getattr(context, 'transcription', [])
            if not transcription:
                logger.warning("No transcription available for segmentation")
                return context
            
            # Get video duration from context or calculate from transcription
            video_duration = getattr(context, 'duration', 0) or \
                          max(t.get('end', 0) for t in transcription) if transcription else 0
            
            # Update progress
            self._update_progress(progress_callback, 1, 4, ProcessingStatus.RUNNING, "Extracting features")
            
            # Extract features from transcription
            features = self._extract_features(transcription, context)
            
            # Update progress
            self._update_progress(progress_callback, 2, 4, ProcessingStatus.RUNNING, "Applying segmentation")
            
            # Apply segmentation
            segments = self.segment_video(
                transcription=transcription,
                video_duration=video_duration,
                audio_features=getattr(context, 'audio_features', None),
                visual_features=getattr(context, 'visual_features', None)
            )
            
            # Update progress
            self._update_progress(progress_callback, 3, 4, ProcessingStatus.RUNNING, "Post-processing segments")
            
            # Post-process segments
            segments = self._post_process_segments(segments, transcription)
            
            # Update context with segments
            context.segments = segments
            
            # Update progress
            self._update_progress(progress_callback, 4, 4, ProcessingStatus.COMPLETED, "Segmentation completed")
            
            logger.info(f"Created {len(segments)} segments")
            return context
            
        except Exception as e:
            error_msg = f"Segmentation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._update_progress(progress_callback, 0, 4, ProcessingStatus.FAILED, error_msg)
            raise PipelineError(error_msg) from e
    
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
                    'min_duration': self.min_segment_duration,
                    'max_duration': self.max_segment_duration
                }
            )
            progress_callback(progress)
    
    def _extract_features(self, transcription: List[Dict], context: Context) -> List[SegmentFeatures]:
        """Extract features from transcription and context."""
        features = []
        
        for i, segment in enumerate(transcription):
            # Calculate pause after this segment
            pause_after = 0.0
            if i < len(transcription) - 1:
                next_start = transcription[i+1].get('start', 0)
                pause_after = max(0, next_start - segment.get('end', 0))
            
            # Check if this segment ends a sentence
            text = segment.get('text', '').strip()
            is_sentence_end = bool(SENTENCE_END.search(text))
            
            feature = SegmentFeatures(
                start_time=segment.get('start', 0),
                end_time=segment.get('end', 0),
                text=text,
                speaker=segment.get('speaker'),
                is_sentence_end=is_sentence_end,
                pause_after=pause_after
            )
            
            # Enrich with context information
            self._enrich_with_context(feature, context)
            
            features.append(feature)
        
        return features
    
    def _enrich_with_context(self, feature: SegmentFeatures, context: Context) -> None:
        """Enrich segment features with context information."""
        # Add silence information if available
        if hasattr(context, 'silent_sections'):
            feature.silence_ratio = self._calculate_silence_ratio(
                feature.start_time,
                feature.end_time,
                context.silent_sections
            )
        
        # Add audio energy if available
        if hasattr(context, 'audio_features'):
            # Simple average energy for the segment
            audio_features = context.audio_features
            start_idx = int(feature.start_time * audio_features.get('sample_rate', 1))
            end_idx = int(feature.end_time * audio_features.get('sample_rate', 1))
            
            if 'energy' in audio_features and end_idx > start_idx:
                segment_energy = audio_features['energy'][start_idx:end_idx]
                if len(segment_energy) > 0:
                    feature.audio_energy = float(np.mean(segment_energy))
        
        # Add visual activity if available
        if hasattr(context, 'visual_features'):
            visual_features = context.visual_features
            frame_rate = visual_features.get('frame_rate', 1)
            start_frame = int(feature.start_time * frame_rate)
            end_frame = int(feature.end_time * frame_rate)
            
            if 'motion' in visual_features and end_frame > start_frame:
                segment_motion = visual_features['motion'][start_frame:end_frame]
                if len(segment_motion) > 0:
                    feature.visual_activity = float(np.mean(segment_motion))
        
        # Add sentiment analysis if TextBlob is available
        if TEXTBLOB_AVAILABLE and feature.text:
            try:
                blob = TextBlob(feature.text)
                feature.sentiment = blob.sentiment.polarity
            except Exception as e:
                logger.warning(f"Sentiment analysis failed: {str(e)}")
        
        # Add TF-IDF vector if scikit-learn is available
        if SKLEARN_AVAILABLE and feature.text:
            try:
                if not hasattr(self, '_fitted_vectorizer'):
                    # Fit the vectorizer on the first call
                    all_text = [f.text for f in getattr(context, 'segments', []) if f.text]
                    if all_text:
                        self.vectorizer.fit(all_text)
                        self._fitted_vectorizer = True
                
                # Transform the current text
                if hasattr(self, '_fitted_vectorizer'):
                    feature.tfidf_vector = self.vectorizer.transform([feature.text])
            except Exception as e:
                logger.warning(f"TF-IDF vectorization failed: {str(e)}")
    
    def _calculate_silence_ratio(self, start: float, end: float, silence_sections: List[Dict]) -> float:
        """
        Calculate the ratio of silence in the given time range.
        
        Args:
            start: Start time in seconds
            end: End time in seconds
            silence_sections: List of silence sections with 'start' and 'end' keys
            
        Returns:
            float: Ratio of silence duration to total duration (0.0 to 1.0)
        """
        if not silence_sections:
            return 0.0
            
        total_duration = end - start
        if total_duration <= 0:
            return 0.0
            
        silence_duration = 0.0
        for silence in silence_sections:
            silence_start = silence.get('start', 0)
            silence_end = silence.get('end', 0)
            
            # Calculate overlap with current time range
            overlap_start = max(start, silence_start)
            overlap_end = min(end, silence_end)
            
            if overlap_end > overlap_start:
                silence_duration += (overlap_end - overlap_start)
        
        return silence_duration / total_duration if total_duration > 0 else 0.0
    
    def _segment_based_on_features(self, features: List[SegmentFeatures], context: Context) -> List[Dict]:
        """
        Create segments based on the extracted features.
        
        Args:
            features: List of segment features
            context: Processing context
            
        Returns:
            List of segment dictionaries
        """
        if not features:
            return []
            
        segments = []
        current_segment = {
            'start': features[0].start_time,
            'end': features[0].end_time,
            'text': features[0].text,
            'speaker': features[0].speaker,
            'sentiment': features[0].sentiment,
            'features': [features[0]]
        }
        
        for i in range(1, len(features)):
            feat = features[i]
            
            # Check if we should start a new segment
            new_segment = False
            
            # Check duration
            duration = feat.end_time - current_segment['start']
            if duration > self.max_segment_duration:
                new_segment = True
            
            # Check for speaker change
            if feat.speaker != current_segment['speaker']:
                new_segment = True
            
            # Check for scene change
            if hasattr(feat, 'scene_change') and feat.scene_change:
                new_segment = True
            
            if new_segment and (feat.end_time - current_segment['start']) >= self.min_segment_duration:
                # Finalize current segment
                segments.append(current_segment)
                # Start new segment
                current_segment = {
                    'start': feat.start_time,
                    'end': feat.end_time,
                    'text': feat.text,
                    'speaker': feat.speaker,
                    'sentiment': feat.sentiment,
                    'features': [feat]
                }
            else:
                # Extend current segment
                current_segment['end'] = feat.end_time
                current_segment['text'] += " " + feat.text
                current_segment['features'].append(feat)
        
        # Add the last segment
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def segment_video(
        self, 
        transcription: List[Dict[str, Any]],
        video_duration: float,
        audio_features: Optional[Dict[str, Any]] = None,
        visual_features: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Create intelligent segments based on content analysis.
        
        Args:
            transcription: List of transcription segments with 'text', 'start', 'end' keys
            video_duration: Total video duration in seconds
            audio_features: Optional audio analysis features
            visual_features: Optional visual analysis features
            
        Returns:
            List of segment dictionaries with 'start', 'end', 'duration', and metadata
        """
        logger.info("Creating intelligent content-aware segments...")
        
        if not transcription:
            logger.warning("No transcription available. Using time-based segmentation.")
            return self._create_time_based_segments(video_duration)
        
        try:
            # Step 1: Detect topic changes
            topic_boundaries = self._detect_topic_changes(transcription)
            
            # Step 2: Detect speaker changes (if possible)
            speaker_boundaries = self._detect_speaker_changes(transcription, audio_features)
            
            # Step 3: Detect natural pause boundaries
            pause_boundaries = self._detect_pause_boundaries(transcription)
            
            # Step 4: Combine all boundary signals
            all_boundaries = self._combine_boundaries(
                topic_boundaries, speaker_boundaries, pause_boundaries
            )
            
            # Step 5: Create segments from boundaries
            segments = self._create_segments_from_boundaries(
                all_boundaries, transcription, video_duration
            )
            
            # Step 6: Post-process segments (merge short, split long)
            segments = self._post_process_segments(segments, transcription)
            
            logger.info(f"Created {len(segments)} intelligent segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error in intelligent segmentation: {e}")
            logger.info("Falling back to time-based segmentation")
            return self._create_time_based_segments(video_duration)
    
    def _detect_topic_changes(self, transcription: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect topic changes using semantic similarity analysis."""
        if not SKLEARN_AVAILABLE or len(transcription) < 2:
            return []
            
        logger.info("Detecting topic changes...")
        
        # Extract text from segments
        texts = [seg.get('text', '').strip() for seg in transcription]
        texts = [t for t in texts if t]  # Remove empty texts
        
        if len(texts) < 2:
            return []
        
        try:
            # Create TF-IDF vectors
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Calculate similarity between consecutive segments
            boundaries = []
            
            for i in range(len(texts) - 1):
                # Calculate cosine similarity between consecutive segments
                sim = cosine_similarity(
                    tfidf_matrix[i:i+1], 
                    tfidf_matrix[i+1:i+2]
                )[0][0]
                
                # If similarity is below threshold, it's a topic change
                if sim < self.semantic_threshold:
                    boundary_time = transcription[i].get('end', 0)
                    boundaries.append({
                        'time': boundary_time,
                        'type': 'topic_change',
                        'confidence': 1 - sim,  # Lower similarity = higher confidence
                        'prev_text': texts[i][:50] + "..." if len(texts[i]) > 50 else texts[i],
                        'next_text': texts[i+1][:50] + "..." if len(texts[i+1]) > 50 else texts[i+1]
                    })
            
            logger.info(f"Found {len(boundaries)} topic changes")
            return boundaries
            
        except Exception as e:
            logger.error(f"Error in topic change detection: {e}")
            return []
    
    def _detect_speaker_changes(
        self, 
        transcription: List[Dict[str, Any]], 
        audio_features: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Detect potential speaker changes using audio and text cues."""
        logger.info("Detecting speaker changes...")
        
        boundaries = []
        
        # Method 1: Audio-based detection (if audio features available)
        if audio_features and 'spectral_centroid' in audio_features:
            boundaries.extend(self._audio_based_speaker_detection(transcription, audio_features))
        
        # Method 2: Text-based detection (style changes)
        if TEXTBLOB_AVAILABLE:
            boundaries.extend(self._text_based_speaker_detection(transcription))
        
        # Method 3: Pause-based detection
        boundaries.extend(self._pause_based_speaker_detection(transcription))
        
        logger.info(f"Found {len(boundaries)} potential speaker changes")
        return boundaries
    
    def _audio_based_speaker_detection(
        self, 
        transcription: List[Dict[str, Any]], 
        audio_features: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect speaker changes using audio features."""
        boundaries = []
        
        try:
            spectral_centroid = np.array(audio_features.get('spectral_centroid', []))
            times = np.array(audio_features.get('times', []))
            
            if len(spectral_centroid) < 2 or len(times) < 2:
                return boundaries
            
            # Simple peak detection for spectral centroid changes
            diff = np.abs(np.diff(spectral_centroid))
            threshold = np.percentile(diff, 85)  # Top 15% of changes
            
            for i in range(len(diff)):
                if diff[i] > threshold and i < len(times):
                    boundaries.append({
                        'time': times[i],
                        'type': 'speaker_change_audio',
                        'confidence': min(1.0, diff[i] / threshold),
                        'spectral_change': float(diff[i])
                    })
            
        except Exception as e:
            logger.error(f"Error in audio-based speaker detection: {e}")
        
        return boundaries
    
    def _text_based_speaker_detection(self, transcription: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect speaker changes using text style and content analysis."""
        boundaries = []
        
        try:
            for i in range(1, len(transcription)):
                prev_text = transcription[i-1].get('text', '').strip()
                curr_text = transcription[i].get('text', '').strip()
                
                if not prev_text or not curr_text:
                    continue
                
                # Check for greeting/introduction patterns
                greetings = ['hello', 'hi', 'welcome', 'thanks', 'thank you', 'good morning', 'good afternoon']
                if any(greeting in curr_text.lower()[:20] for greeting in greetings):
                    boundaries.append({
                        'time': transcription[i].get('start', 0),
                        'type': 'speaker_change_greeting',
                        'confidence': 0.7,
                        'text_cue': curr_text[:30]
                    })
                
                # Check for sentiment/style changes
                prev_sentiment = TextBlob(prev_text).sentiment.polarity
                curr_sentiment = TextBlob(curr_text).sentiment.polarity
                
                if abs(prev_sentiment - curr_sentiment) > 0.5:
                    boundaries.append({
                        'time': transcription[i].get('start', 0),
                        'type': 'speaker_change_sentiment',
                        'confidence': 0.5,
                        'sentiment_change': abs(prev_sentiment - curr_sentiment)
                    })
        
        except Exception as e:
            logger.error(f"Error in text-based speaker detection: {e}")
        
        return boundaries
    
    def _pause_based_speaker_detection(self, transcription: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect speaker changes based on pause duration patterns."""
        boundaries = []
        
        try:
            for i in range(1, len(transcription)):
                prev_end = transcription[i-1].get('end', 0)
                curr_start = transcription[i].get('start', 0)
                pause_duration = curr_start - prev_end
                
                # Long pauses (>2 seconds) often indicate speaker changes
                if pause_duration > 2.0:
                    confidence = min(1.0, pause_duration / 5.0)  # Max confidence at 5+ seconds
                    boundaries.append({
                        'time': curr_start,
                        'type': 'speaker_change_pause',
                        'confidence': confidence,
                        'pause_duration': pause_duration
                    })
        
        except Exception as e:
            logger.error(f"Error in pause-based speaker detection: {e}")
        
        return boundaries
    
    def _detect_pause_boundaries(self, transcription: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect natural pause boundaries that could serve as segment breaks."""
        logger.info("Detecting natural pause boundaries...")
        boundaries = []
        
        try:
            for i in range(1, len(transcription)):
                prev_end = transcription[i-1].get('end', 0)
                curr_start = transcription[i].get('start', 0)
                pause_duration = curr_start - prev_end
                
                # Natural pauses (0.5-2 seconds) are good segment boundaries
                if 0.5 <= pause_duration <= 2.0:
                    # Check if the pause is at a sentence boundary
                    prev_text = transcription[i-1].get('text', '').strip()
                    sentence_endings = ['.', '!', '?', '...']
                    
                    is_sentence_boundary = any(prev_text.endswith(ending) for ending in sentence_endings)
                    confidence = 0.8 if is_sentence_boundary else 0.4
                    confidence *= min(1.0, pause_duration / 1.0)  # Longer pauses = higher confidence
                    
                    boundaries.append({
                        'time': curr_start,
                        'type': 'natural_pause',
                        'confidence': confidence,
                        'pause_duration': pause_duration,
                        'sentence_boundary': is_sentence_boundary
                    })
        
        except Exception as e:
            logger.error(f"Error in pause boundary detection: {e}")
        
        return boundaries
    
    def _combine_boundaries(
        self, 
        topic_boundaries: List[Dict[str, Any]],
        speaker_boundaries: List[Dict[str, Any]], 
        pause_boundaries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine and weight different types of boundaries."""
        logger.info("Combining boundary signals...")
        
        all_boundaries = []
        
        # Add topic boundaries with high weight
        for boundary in topic_boundaries:
            boundary['weighted_confidence'] = boundary['confidence'] * self.topic_change_weight
            all_boundaries.append(boundary)
        
        # Add speaker boundaries with medium weight
        for boundary in speaker_boundaries:
            boundary['weighted_confidence'] = boundary['confidence'] * self.speaker_change_weight
            all_boundaries.append(boundary)
        
        # Add pause boundaries with lower weight
        for boundary in pause_boundaries:
            boundary['weighted_confidence'] = boundary['confidence'] * 0.3
            all_boundaries.append(boundary)
        
        # Remove duplicates (boundaries within 1 second of each other)
        all_boundaries.sort(key=lambda x: x['time'])
        filtered_boundaries = []
        
        for boundary in all_boundaries:
            # Check if we already have a boundary very close to this one
            is_duplicate = any(
                abs(existing['time'] - boundary['time']) < 1.0
                for existing in filtered_boundaries
            )
            
            if not is_duplicate:
                filtered_boundaries.append(boundary)
            else:
                # Merge with existing boundary if this one has higher confidence
                for existing in filtered_boundaries:
                    if abs(existing['time'] - boundary['time']) < 1.0:
                        if boundary['weighted_confidence'] > existing['weighted_confidence']:
                            existing.update(boundary)
                        break
        
        # Sort by weighted confidence (keep best boundaries)
        filtered_boundaries.sort(key=lambda x: x['weighted_confidence'], reverse=True)
        
        logger.info(f"Combined into {len(filtered_boundaries)} boundary candidates")
        return filtered_boundaries
    
    def _create_segments_from_boundaries(
        self, 
        boundaries: List[Dict[str, Any]], 
        transcription: List[Dict[str, Any]],
        video_duration: float
    ) -> List[Dict[str, Any]]:
        """Create segments using the detected boundaries."""
        logger.info("Creating segments from boundaries...")
        
        if not boundaries:
            return self._create_time_based_segments(video_duration)
        
        # Start with high-confidence boundaries
        selected_boundaries = [0.0]  # Always start at beginning
        
        for boundary in boundaries:
            # Only use boundaries with sufficient confidence
            if boundary['weighted_confidence'] > 0.3:
                boundary_time = boundary['time']
                
                # Ensure minimum segment duration
                if boundary_time - selected_boundaries[-1] >= self.min_segment_duration:
                    selected_boundaries.append(boundary_time)
        
        # Always end at video duration
        if selected_boundaries[-1] < video_duration:
            selected_boundaries.append(video_duration)
        
        # Create segments from boundaries
        segments = []
        for i in range(len(selected_boundaries) - 1):
            start_time = selected_boundaries[i]
            end_time = selected_boundaries[i + 1]
            
            # Get transcription for this segment
            segment_transcription = [
                seg for seg in transcription
                if seg.get('start', 0) >= start_time and seg.get('end', 0) <= end_time
            ]
            
            # Calculate segment features
            segment_text = ' '.join(seg.get('text', '') for seg in segment_transcription)
            word_count = len(segment_text.split())
            
            segments.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'transcription': segment_transcription,
                'text': segment_text,
                'word_count': word_count,
                'type': 'intelligent_segment'
            })
        
        return segments
    
    def _post_process_segments(
        self, 
        segments: List[Dict[str, Any]], 
        transcription: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Post-process segments to merge short ones and split long ones."""
        logger.info("Post-processing segments...")
        
        processed_segments = []
        
        i = 0
        while i < len(segments):
            segment = segments[i]
            
            # If segment is too short, try to merge with next
            if (segment['duration'] < self.min_segment_duration and 
                i < len(segments) - 1):
                
                next_segment = segments[i + 1]
                
                # Merge segments
                merged_segment = {
                    'start': segment['start'],
                    'end': next_segment['end'],
                    'duration': next_segment['end'] - segment['start'],
                    'transcription': segment['transcription'] + next_segment['transcription'],
                    'text': segment['text'] + ' ' + next_segment['text'],
                    'word_count': segment['word_count'] + next_segment['word_count'],
                    'type': 'merged_segment'
                }
                
                processed_segments.append(merged_segment)
                i += 2  # Skip next segment since we merged it
                
            # If segment is too long, split it
            elif segment['duration'] > self.max_segment_duration:
                # Simple split in half for now
                mid_point = (segment['start'] + segment['end']) / 2
                
                # Find the closest transcription boundary to mid_point
                if segment['transcription']:
                    mid_segments = sorted(
                        segment['transcription'],
                        key=lambda x: abs((x['start'] + x['end']) / 2 - mid_point)
                    )
                    if mid_segments:
                        mid_point = (mid_segments[0]['start'] + mid_segments[0]['end']) / 2
                
                # Create two segments
                first_half = {
                    **segment,
                    'end': mid_point,
                    'duration': mid_point - segment['start'],
                    'transcription': [s for s in segment['transcription'] 
                                    if s['end'] <= mid_point],
                    'type': 'split_segment_first_half'
                }
                
                second_half = {
                    **segment,
                    'start': mid_point,
                    'duration': segment['end'] - mid_point,
                    'transcription': [s for s in segment['transcription'] 
                                    if s['start'] >= mid_point],
                    'type': 'split_segment_second_half'
                }
                
                processed_segments.extend([first_half, second_half])
                i += 1
                
            else:
                processed_segments.append(segment)
                i += 1
        
        logger.info(f"Post-processing: {len(segments)} -> {len(processed_segments)} segments")
        return processed_segments
    
    def _create_time_based_segments(self, video_duration: float) -> List[Dict[str, Any]]:
        """Fallback method to create time-based segments when content analysis fails."""
        logger.info("Creating fallback time-based segments...")
        
        target_duration = (self.min_segment_duration + self.max_segment_duration) / 2
        num_segments = max(1, int(round(video_duration / target_duration)))
        segment_duration = video_duration / num_segments
        
        segments = []
        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = (i + 1) * segment_duration if i < num_segments - 1 else video_duration
            
            segments.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'transcription': [],
                'text': '',
                'word_count': 0,
                'type': 'time_based_segment'
            })
        
        return segments
