"""
Feature extraction for video segment ranking.

This module provides functionality to extract features from video segments
for use in the learned ranking model.
"""
from typing import Dict, List, Any, Optional, Union
import numpy as np
from dataclasses import asdict
from pathlib import Path
import logging

from app.editing.pipeline.core import Context, Segment
from app.editing.analyzers import get_analyzer

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """
    Extracts features from video segments for ranking.
    
    This class handles the extraction of features from video segments,
    combining information from different analyzers into a consistent
    feature vector for each segment.
    """
    
    def __init__(self, analyzers: Optional[Dict[str, Any]] = None):
        """
        Initialize the feature extractor.
        
        Args:
            analyzers: Dictionary mapping analyzer names to their configurations.
                      If None, default analyzers will be used.
        """
        self.analyzers = analyzers or {
            'audio': {'sample_rate': 16000},
            'visual': {'frame_rate': 2.0},
            'content': {}
        }
        self._analyzer_instances = {}
    
    async def initialize(self) -> None:
        """Initialize all analyzer instances."""
        from app.editing.analyzers import get_analyzer
        
        for name, config in self.analyzers.items():
            try:
                analyzer = get_analyzer(name, **config)
                await analyzer.initialize()
                self._analyzer_instances[name] = analyzer
                logger.info(f"Initialized analyzer: {name}")
            except Exception as e:
                logger.warning(f"Failed to initialize analyzer {name}: {e}")
    
    async def cleanup(self) -> None:
        """Clean up analyzer instances."""
        for analyzer in self._analyzer_instances.values():
            try:
                await analyzer.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up analyzer: {e}")
        self._analyzer_instances.clear()
    
    async def extract_features(
        self,
        context: Context,
        segment: Segment,
        video_path: Union[str, Path],
        **kwargs
    ) -> Dict[str, float]:
        """
        Extract features for a single segment.
        
        Args:
            context: The processing context
            segment: The segment to extract features for
            video_path: Path to the source video file
            **kwargs: Additional arguments to pass to analyzers
            
        Returns:
            Dictionary of feature names to values
        """
        features = {}
        
        # Basic segment features
        features.update(self._extract_basic_features(segment, context))
        
        # Run analyzers
        for name, analyzer in self._analyzer_instances.items():
            try:
                if name == 'audio':
                    audio_features = await self._extract_audio_features(
                        analyzer, video_path, segment, context, **kwargs
                    )
                    features.update(audio_features)
                
                elif name == 'visual':
                    visual_features = await self._extract_visual_features(
                        analyzer, video_path, segment, context, **kwargs
                    )
                    features.update(visual_features)
                
                elif name == 'content':
                    content_features = await self._extract_content_features(
                        analyzer, video_path, segment, context, **kwargs
                    )
                    features.update(content_features)
                
            except Exception as e:
                logger.warning(f"Error in {name} analyzer: {e}", exc_info=True)
        
        return features
    
    def _extract_basic_features(
        self,
        segment: Segment,
        context: Context
    ) -> Dict[str, float]:
        """Extract basic segment features."""
        return {
            # Temporal features
            'segment_duration': segment.duration,
            'segment_start': segment.start,
            'segment_end': segment.end,
            'segment_position': segment.start / context.video_duration if context.video_duration > 0 else 0,
            'segment_normalized_duration': segment.duration / context.video_duration if context.video_duration > 0 else 0,
            
            # Scene and silence features
            'has_scene_change': float(segment.annotations.get('scene_change', False)),
            'is_scene_boundary': float(segment.annotations.get('is_scene_boundary', False)),
            'silence_ratio': float(segment.annotations.get('silence_ratio', 0.0)),
            'is_silent': float(segment.annotations.get('is_silent', False)),
            
            # Existing scores
            'audio_score': float(segment.scores.get('audio', 0.0)),
            'visual_score': float(segment.scores.get('visual', 0.0)),
            'content_score': float(segment.scores.get('content', 0.0)),
            'overall_score': float(segment.overall_score or 0.0)
        }
    
    async def _extract_audio_features(
        self,
        analyzer: Any,
        video_path: Union[str, Path],
        segment: Segment,
        context: Context,
        **kwargs
    ) -> Dict[str, float]:
        """Extract audio features for a segment."""
        # Create a temporary video clip for this segment
        from tempfile import NamedTemporaryFile
        import subprocess
        
        with NamedTemporaryFile(suffix='.wav') as temp_audio:
            # Extract audio for just this segment
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-ss', str(segment.start),
                '-t', str(segment.duration),
                '-i', str(video_path),
                '-vn',  # Disable video
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',  # Mono
                '-f', 'wav',
                temp_audio.name
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                
                # Analyze the audio segment
                result = await analyzer.analyze(Path(temp_audio.name))
                
                # Prefix audio features
                return {
                    f'audio_{k}': float(v) 
                    for k, v in result.features.items()
                    if isinstance(v, (int, float, bool))
                }
                
            except (subprocess.CalledProcessError, Exception) as e:
                logger.warning(f"Audio feature extraction failed: {e}")
                return {}
    
    async def _extract_visual_features(
        self,
        analyzer: Any,
        video_path: Union[str, Path],
        segment: Segment,
        context: Context,
        **kwargs
    ) -> Dict[str, float]:
        """Extract visual features for a segment."""
        # Create a temporary video clip for this segment
        from tempfile import NamedTemporaryFile
        import subprocess
        
        with NamedTemporaryFile(suffix='.mp4') as temp_video:
            # Extract video segment
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-ss', str(segment.start),
                '-t', str(segment.duration),
                '-i', str(video_path),
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'veryfast',
                '-an',  # No audio
                temp_video.name
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                
                # Analyze the video segment
                result = await analyzer.analyze(Path(temp_video.name))
                
                # Prefix visual features
                return {
                    f'visual_{k}': float(v) 
                    for k, v in result.features.items()
                    if isinstance(v, (int, float, bool))
                }
                
            except (subprocess.CalledProcessError, Exception) as e:
                logger.warning(f"Visual feature extraction failed: {e}")
                return {}
    
    async def _extract_content_features(
        self,
        analyzer: Any,
        video_path: Union[str, Path],
        segment: Segment,
        context: Context,
        **kwargs
    ) -> Dict[str, float]:
        """Extract content features for a segment."""
        # Check for transcript in context
        transcript = None
        if hasattr(context, 'transcript') and context.transcript:
            # Filter transcript for this segment
            transcript_segments = [
                t for t in context.transcript
                if (t.get('start', float('inf')) >= segment.start and 
                     t.get('end', 0) <= segment.end)
            ]
            transcript = ' '.join(t.get('text', '') for t in transcript_segments)
        
        # If no transcript, try to extract from video
        if not transcript and hasattr(segment, 'text') and segment.text:
            transcript = segment.text
        
        # If we have a transcript, analyze it
        if transcript:
            try:
                result = await analyzer.analyze(
                    video_path,
                    transcript=transcript,
                    duration=segment.duration
                )
                
                # Prefix content features
                return {
                    f'content_{k}': float(v) 
                    for k, v in result.features.items()
                    if isinstance(v, (int, float, bool))
                }
                
            except Exception as e:
                logger.warning(f"Content feature extraction failed: {e}")
        
        return {}
