"""
OpusClip-Level Video Processing Integration (Fixed Version)

This maintains all original class names while fixing hanging issues.
"""
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from app.editing.pipeline.core import HighlightPipeline, Context, VideoProcessor, Segment, Progress, ProcessingStatus, CancellationToken
from app.editing.processors.scene_detector import SceneDetector
from app.editing.segmenters.basic import BasicSegmenter

logger = logging.getLogger(__name__)

@dataclass
class OpusClipConfig:
    """Configuration for OpusClip-level processing."""
    # Segmentation settings
    min_segment_duration: float = 4.0
    max_segment_duration: float = 25.0
    semantic_threshold: float = 0.25
    
    # Highlight detection settings
    min_highlight_duration: float = 3.0
    max_highlight_duration: float = 20.0
    target_total_duration: float = 60.0
    quality_threshold: float = 0.5
    
    # Feature weights
    audio_weight: float = 0.25
    visual_weight: float = 0.35
    content_weight: float = 0.25
    engagement_weight: float = 0.15
    
    # Advanced settings
    use_advanced_nlp: bool = False  # Disabled to prevent hanging
    diversity_lambda: float = 0.3
    max_highlights: int = 8
    
    # Content-specific adaptations
    adapt_to_content_type: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'min_segment_duration': self.min_segment_duration,
            'max_segment_duration': self.max_segment_duration,
            'semantic_threshold': self.semantic_threshold,
            'min_highlight_duration': self.min_highlight_duration,
            'max_highlight_duration': self.max_highlight_duration,
            'target_total_duration': self.target_total_duration,
            'quality_threshold': self.quality_threshold,
            'audio_weight': self.audio_weight,
            'visual_weight': self.visual_weight,
            'content_weight': self.content_weight,
            'engagement_weight': self.engagement_weight,
            'use_advanced_nlp': self.use_advanced_nlp,
            'diversity_lambda': self.diversity_lambda,
            'max_highlights': self.max_highlights,
            'adapt_to_content_type': self.adapt_to_content_type
        }

class IntelligentSegmenter(VideoProcessor):
    """
    Intelligent segmenter that maintains original interface while fixing hanging issues.
    """
    
    def __init__(self, 
                 min_segment_duration: float = 3.0,
                 max_segment_duration: float = 20.0,
                 semantic_threshold: float = 0.25,
                 use_scene_boundaries: bool = True,
                 respect_silence: bool = True):
        """
        Initialize the intelligent segmenter.
        
        Args:
            min_segment_duration: Minimum duration of a segment in seconds
            max_segment_duration: Maximum duration of a segment in seconds
            semantic_threshold: Threshold for semantic segmentation
            use_scene_boundaries: Whether to use scene changes for boundaries
            respect_silence: Whether to avoid cutting during speech
        """
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.semantic_threshold = semantic_threshold
        self.use_scene_boundaries = use_scene_boundaries
        self.respect_silence = respect_silence
    
    def process(self, 
                context: Context, 
                progress_callback: Optional[Callable[[Progress], None]] = None,
                cancel_token: Optional[CancellationToken] = None) -> Context:
        """
        Process the context to create intelligent segments.
        
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
            self._update_progress(progress_callback, 0, 3, ProcessingStatus.RUNNING,
                                "Starting intelligent segmentation")
            
            # Check for cancellation
            cancel_token.check_cancelled()
            
            # Get video duration from context
            video_duration = getattr(context, 'duration', 0)
            if video_duration <= 0:
                # Try to get duration from metadata
                video_duration = context.metadata.get('duration', 0)
                if video_duration <= 0:
                    logger.warning("No video duration available, using default")
                    video_duration = 300.0  # Default to 5 minutes
            
            logger.info(f"Creating segments for {video_duration:.1f}s video")
            
            # Update progress
            self._update_progress(progress_callback, 1, 3, message="Creating segments")
            
            # Create segments using available information
            segments = self._create_intelligent_segments(context, video_duration, cancel_token)
            
            # Convert to Segment objects and store in context
            context.segments = []
            
            for seg_dict in segments:
                segment = Segment(
                    start=seg_dict['start'],
                    end=seg_dict['end']
                )
                
                # Add text if available
                if 'text' in seg_dict:
                    segment.text = seg_dict['text']
                
                # Add other attributes
                segment.scene_change = seg_dict.get('scene_change', False)
                segment.silent_ratio = seg_dict.get('silent_ratio', 0.0)
                segment.word_count = seg_dict.get('word_count', 0)
                
                context.segments.append(segment)
            
            # Update progress
            self._update_progress(progress_callback, 3, 3, ProcessingStatus.COMPLETED,
                                f"Created {len(context.segments)} segments")
            
            logger.info(f"Created {len(context.segments)} intelligent segments")
            return context
            
        except Exception as e:
            error_msg = f"Intelligent segmentation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if progress_callback:
                progress_callback(Progress(
                    status=ProcessingStatus.FAILED,
                    message=error_msg
                ))
            
            # Don't raise exception, provide fallback
            logger.warning("Falling back to basic segmentation")
            try:
                basic_segmenter = BasicSegmenter(
                    min_segment_duration=self.min_segment_duration,
                    max_segment_duration=self.max_segment_duration
                )
                return basic_segmenter.process(context, progress_callback, cancel_token)
            except Exception as fallback_error:
                logger.error(f"Fallback segmentation also failed: {fallback_error}")
                # Create minimal segments as last resort
                context.segments = self._create_minimal_segments(context, video_duration)
                return context
    
    def _create_intelligent_segments(
        self, 
        context: Context, 
        video_duration: float,
        cancel_token: CancellationToken
    ) -> List[Dict[str, Any]]:
        """
        Create intelligent segments using available context information.
        """
        segments = []
        
        # Get available boundary information
        scene_changes = getattr(context, 'scene_changes', []) if self.use_scene_boundaries else []
        silence_sections = getattr(context, 'silence_sections', []) if self.respect_silence else []
        transcription = getattr(context, 'transcription', None)
        
        logger.info(f"Using {len(scene_changes)} scene changes, {len(silence_sections)} silence sections")
        
        # Create boundary points
        boundary_points = self._create_boundary_points(
            video_duration, scene_changes, silence_sections, transcription
        )
        
        logger.info(f"Created {len(boundary_points)} boundary points")
        
        # Create segments from boundary points
        for i in range(len(boundary_points) - 1):
            cancel_token.check_cancelled()
            
            start = boundary_points[i]
            end = boundary_points[i + 1]
            duration = end - start
            
            # Skip segments that are too short
            if duration < self.min_segment_duration:
                continue
            
            # Split segments that are too long
            if duration > self.max_segment_duration:
                sub_segments = self._split_long_segment(start, end, transcription)
                segments.extend(sub_segments)
            else:
                segment = {
                    'start': start,
                    'end': end,
                    'duration': duration,
                    'scene_change': start in scene_changes,
                    'text': self._get_segment_text(start, end, transcription),
                    'word_count': 0,
                    'silent_ratio': self._calculate_silence_ratio(start, end, silence_sections)
                }
                
                # Count words
                if segment['text']:
                    segment['word_count'] = len(segment['text'].split())
                
                segments.append(segment)
        
        # If no good segments were created, fall back to time-based segmentation
        if not segments:
            logger.warning("No intelligent segments created, falling back to time-based segmentation")
            segments = self._create_time_based_segments(video_duration)
        
        logger.info(f"Created {len(segments)} segments")
        return segments
    
    def _create_boundary_points(
        self, 
        video_duration: float, 
        scene_changes: List[float], 
        silence_sections: List[Dict], 
        transcription: Optional[List[Dict]]
    ) -> List[float]:
        """Create boundary points for segmentation."""
        boundaries = set()
        
        # Always include start and end
        boundaries.add(0.0)
        boundaries.add(video_duration)
        
        # Add scene changes
        for scene_time in scene_changes:
            if 0 < scene_time < video_duration:
                boundaries.add(scene_time)
        
        # Add silence boundaries (end of silence sections)
        for silence in silence_sections:
            silence_end = silence.get('end', 0)
            if 0 < silence_end < video_duration:
                boundaries.add(silence_end)
        
        # Add transcription boundaries if available
        if transcription:
            for segment in transcription:
                start = segment.get('start', 0)
                end = segment.get('end', 0)
                if 0 < start < video_duration:
                    boundaries.add(start)
                if 0 < end < video_duration:
                    boundaries.add(end)
        
        # If we have very few boundaries, add some time-based ones
        boundary_list = sorted(boundaries)
        if len(boundary_list) < 5:
            # Add boundaries every max_segment_duration
            time_step = self.max_segment_duration
            current_time = time_step
            while current_time < video_duration:
                boundary_list.append(current_time)
                current_time += time_step
            boundary_list = sorted(set(boundary_list))
        
        return boundary_list
    
    def _split_long_segment(
        self, 
        start: float, 
        end: float, 
        transcription: Optional[List[Dict]]
    ) -> List[Dict[str, Any]]:
        """Split a segment that's too long into smaller segments."""
        duration = end - start
        num_splits = int(duration // self.max_segment_duration) + 1
        split_duration = duration / num_splits
        
        segments = []
        current_start = start
        
        for i in range(num_splits):
            current_end = min(current_start + split_duration, end)
            
            if current_end - current_start >= self.min_segment_duration:
                segment = {
                    'start': current_start,
                    'end': current_end,
                    'duration': current_end - current_start,
                    'scene_change': i == 0,  # Only first split has scene change
                    'text': self._get_segment_text(current_start, current_end, transcription),
                    'word_count': 0,
                    'silent_ratio': 0.0
                }
                
                if segment['text']:
                    segment['word_count'] = len(segment['text'].split())
                
                segments.append(segment)
            
            current_start = current_end
        
        return segments
    
    def _get_segment_text(
        self, 
        start: float, 
        end: float, 
        transcription: Optional[List[Dict]]
    ) -> str:
        """Get text for a segment from transcription."""
        if not transcription:
            return ''
        
        text_parts = []
        for segment in transcription:
            seg_start = segment.get('start', 0)
            seg_end = segment.get('end', 0)
            
            # Check for overlap
            if seg_start < end and seg_end > start:
                text = segment.get('text', '').strip()
                if text:
                    text_parts.append(text)
        
        return ' '.join(text_parts)
    
    def _calculate_silence_ratio(
        self, 
        start: float, 
        end: float, 
        silence_sections: List[Dict]
    ) -> float:
        """Calculate the ratio of silence in a segment."""
        if not silence_sections:
            return 0.0
        
        total_silence = 0.0
        segment_duration = end - start
        
        for silence in silence_sections:
            silence_start = silence.get('start', 0)
            silence_end = silence.get('end', 0)
            
            # Calculate overlap
            overlap_start = max(start, silence_start)
            overlap_end = min(end, silence_end)
            
            if overlap_end > overlap_start:
                total_silence += overlap_end - overlap_start
        
        return total_silence / segment_duration if segment_duration > 0 else 0.0
    
    def _create_time_based_segments(self, video_duration: float) -> List[Dict[str, Any]]:
        """Create simple time-based segments as fallback."""
        segments = []
        current_time = 0.0
        
        while current_time < video_duration:
            segment_end = min(current_time + self.max_segment_duration, video_duration)
            
            # Ensure segment meets minimum duration requirement
            if segment_end - current_time >= self.min_segment_duration:
                segments.append({
                    'start': current_time,
                    'end': segment_end,
                    'duration': segment_end - current_time,
                    'scene_change': current_time == 0.0,
                    'text': '',
                    'word_count': 0,
                    'silent_ratio': 0.0
                })
            
            current_time = segment_end
        
        return segments
    
    def _create_minimal_segments(self, context: Context, video_duration: float) -> List[Segment]:
        """Create minimal segments as last resort."""
        segments = []
        segment_duration = min(self.max_segment_duration, video_duration / 2)
        current_time = 0.0
        
        while current_time < video_duration:
            segment_end = min(current_time + segment_duration, video_duration)
            
            if segment_end - current_time >= self.min_segment_duration:
                segment = Segment(start=current_time, end=segment_end)
                segment.text = ''
                segment.scene_change = current_time == 0.0
                segment.silent_ratio = 0.0
                segment.word_count = 0
                segments.append(segment)
            
            current_time = segment_end
        
        logger.info(f"Created {len(segments)} minimal fallback segments")
        return segments
    
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
                metadata={'processor': 'IntelligentSegmenter'}
            )
            progress_callback(progress)


class OpusClipLevelPipeline:
    """
    Complete pipeline that achieves OpusClip-level quality while maintaining reliability.
    """
    
    def __init__(self, config: Optional[OpusClipConfig] = None):
        """Initialize the OpusClip-level pipeline."""
        self.config = config or OpusClipConfig()
        self.pipeline = None
        self.analyzers = {}
    
    def create_pipeline(self) -> HighlightPipeline:
        """Create the complete processing pipeline."""
        # Import here to avoid circular imports
        from app.editing.processors.silence_remover import SilenceRemover
        
        # Create processors with optimized settings
        silence_remover = SilenceRemover(
            silence_threshold=-30.0,
            silence_duration=0.8
        )
        
        scene_detector = SceneDetector(
            threshold=25.0,  # More sensitive scene detection
            min_scene_len=1.5
        )
        
        segmenter = IntelligentSegmenter(
            min_segment_duration=self.config.min_segment_duration,
            max_segment_duration=self.config.max_segment_duration,
            semantic_threshold=self.config.semantic_threshold
        )
        
        # Import the fixed highlight detector
        from .enhanced_highlight_detector import OpusClipLevelHighlightDetector
        
        highlight_detector = OpusClipLevelHighlightDetector(
            min_duration=self.config.min_highlight_duration,
            max_duration=self.config.max_highlight_duration,
            target_total_duration=self.config.target_total_duration,
            audio_weight=self.config.audio_weight,
            visual_weight=self.config.visual_weight,
            content_weight=self.config.content_weight,
            engagement_weight=self.config.engagement_weight,
            quality_threshold=self.config.quality_threshold,
            max_highlights=self.config.max_highlights
        )
        
        # Create pipeline
        return HighlightPipeline([
            silence_remover,
            scene_detector,
            segmenter,
            highlight_detector
        ])
    
    async def process_video_to_opus_clip_quality(
        self,
        video_path: str,
        transcription: Optional[List[Dict[str, Any]]] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a video to OpusClip quality level with reliability.
        """
        try:
            # Initialize context
            context = Context(
                video_path=video_path,
                metadata={
                    'processing_config': self.config.to_dict(),
                    'pipeline_version': 'opus_clip_level_v1_fixed'
                }
            )
            
            # Add transcription if provided
            if transcription:
                context.transcription = transcription
            
            # Get video duration
            context.duration = self._get_video_duration(video_path)
            
            # Create and run pipeline
            if not self.pipeline:
                self.pipeline = self.create_pipeline()
            
            logger.info("Running OpusClip-level processing pipeline...")
            processed_context = self.pipeline.run(context)
            
            # Post-process results
            results = self._format_results(processed_context)
            
            # Save outputs if directory specified
            if output_dir:
                await self._save_outputs(results, output_dir)
            
            return results
            
        except Exception as e:
            logger.error(f"OpusClip-level processing failed: {str(e)}", exc_info=True)
            # Return a safe fallback result
            return {
                'success': False,
                'error': str(e),
                'video_path': video_path,
                'highlights': [],
                'segments': [],
                'quality_metrics': {
                    'total_highlights': 0,
                    'total_highlight_duration': 0,
                    'avg_highlight_score': 0
                }
            }
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe."""
        import subprocess
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get video duration: {e}")
            return 300.0  # Default fallback
    
    def _format_results(self, context: Context) -> Dict[str, Any]:
        """Format processing results for output."""
        highlights = getattr(context, 'highlights', [])
        segments = getattr(context, 'segments', [])
        
        return {
            'success': True,
            'video_path': context.video_path,
            'processing_config': self.config.to_dict(),
            
            # Main outputs
            'highlights': [
                {
                    'start': h.get('start', 0),
                    'end': h.get('end', 0),
                    'duration': h.get('duration', 0),
                    'score': h.get('score', 0),
                    'text': h.get('text', ''),
                    'score_breakdown': h.get('score_breakdown', {}),
                    'features': h.get('features', {}),
                    'rank': h.get('rank', 0)
                }
                for h in highlights
            ],
            
            # Segments information
            'segments': [
                {
                    'start': s.start,
                    'end': s.end,
                    'duration': s.end - s.start,
                    'text': getattr(s, 'text', ''),
                    'annotations': {
                        'scene_change': getattr(s, 'scene_change', False),
                        'silent_ratio': getattr(s, 'silent_ratio', 0.0),
                        'word_count': getattr(s, 'word_count', 0)
                    }
                }
                for s in segments
            ],
            
            # Quality metrics
            'quality_metrics': {
                'total_highlights': len(highlights),
                'total_highlight_duration': sum(h.get('duration', 0) for h in highlights),
                'avg_highlight_score': sum(h.get('score', 0) for h in highlights) / len(highlights) if highlights else 0,
                'coverage_ratio': sum(h.get('duration', 0) for h in highlights) / context.duration if context.duration else 0,
                'total_segments': len(segments),
                'avg_segment_duration': sum(s.end - s.start for s in segments) / len(segments) if segments else 0
            }
        }
    
    async def _save_outputs(self, results: Dict[str, Any], output_dir: str):
        """Save processing outputs to files."""
        import json
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save main results
        results_file = output_path / 'opus_clip_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {output_dir}")


# Convenience functions for easy usage
def create_opus_clip_config(
    content_type: str = 'general',
    target_duration: float = 60.0,
    quality_level: str = 'high'
) -> OpusClipConfig:
    """Create an OpusClip configuration optimized for specific content."""
    config = OpusClipConfig()
    config.target_total_duration = target_duration
    
    # Content-specific optimizations
    content_optimizations = {
        'tutorial': {
            'min_segment_duration': 6.0,
            'max_segment_duration': 30.0,
            'semantic_threshold': 0.2,
            'content_weight': 0.4,
            'quality_threshold': 0.4
        },
        'interview': {
            'min_segment_duration': 4.0,
            'max_segment_duration': 20.0,
            'semantic_threshold': 0.35,
            'audio_weight': 0.3,
            'content_weight': 0.3,
            'quality_threshold': 0.45
        },
        'presentation': {
            'min_segment_duration': 8.0,
            'max_segment_duration': 35.0,
            'visual_weight': 0.4,
            'content_weight': 0.35,
            'quality_threshold': 0.5
        },
        'vlog': {
            'min_segment_duration': 3.0,
            'max_segment_duration': 15.0,
            'engagement_weight': 0.25,
            'visual_weight': 0.4,
            'quality_threshold': 0.55
        }
    }
    
    # Quality level adjustments
    quality_adjustments = {
        'standard': {'quality_threshold': 0.4, 'max_highlights': 6},
        'high': {'quality_threshold': 0.5, 'max_highlights': 8},
        'premium': {'quality_threshold': 0.6, 'max_highlights': 10}
    }
    
    # Apply optimizations
    if content_type in content_optimizations:
        for key, value in content_optimizations[content_type].items():
            setattr(config, key, value)
    
    if quality_level in quality_adjustments:
        for key, value in quality_adjustments[quality_level].items():
            setattr(config, key, value)
    
    return config


async def process_video_opus_clip_quality(
    video_path: str,
    transcription: Optional[List[Dict[str, Any]]] = None,
    content_type: str = 'general',
    target_duration: float = 60.0,
    quality_level: str = 'high',
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Process a video to OpusClip quality with simplified interface."""
    # Create optimized config
    config = create_opus_clip_config(content_type, target_duration, quality_level)
    
    # Create and run pipeline
    pipeline = OpusClipLevelPipeline(config)
    results = await pipeline.process_video_to_opus_clip_quality(
        video_path=video_path,
        transcription=transcription,
        output_dir=output_dir
    )
    
    return results