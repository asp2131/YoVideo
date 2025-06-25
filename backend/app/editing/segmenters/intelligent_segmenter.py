"""
OpusClip-Level Video Processing Integration

This module demonstrates how to integrate all the advanced components
to achieve OpusClip-level quality for video highlight detection.
"""
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.editing.pipeline.core import HighlightPipeline, Context
from app.editing.processors.scene_detector import SceneDetector
from app.editing.processors.enhanced_highlight_detector import OpusClipLevelHighlightDetector as EnhancedHighlightDetector
from app.editing.analyzers import get_analyzer
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
    use_advanced_nlp: bool = True
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

class OpusClipLevelPipeline:
    """
    Complete pipeline that achieves OpusClip-level quality.
    
    This pipeline includes:
    1. Comprehensive feature analysis
    2. Intelligent content-aware segmentation
    3. Advanced multi-modal highlight detection
    4. Quality optimization and diversity selection
    """
    
    def __init__(self, config: Optional[OpusClipConfig] = None):
        """Initialize the OpusClip-level pipeline."""
        self.config = config or OpusClipConfig()
        self.pipeline = None
        self.analyzers = {}
    
    def create_pipeline(self) -> HighlightPipeline:
        """Create the complete processing pipeline."""
        # Create processors with optimized settings
        scene_detector = SceneDetector(
            threshold=25.0,  # More sensitive scene detection
            min_scene_len=1.5
        )
        
        segmenter = BasicSegmenter(
            min_segment_duration=self.config.min_segment_duration,
            max_segment_duration=self.config.max_segment_duration
        )
        
        highlight_detector = EnhancedHighlightDetector(
            min_duration=self.config.min_highlight_duration,
            max_duration=self.config.max_highlight_duration,
            target_total_duration=self.config.target_total_duration,
            audio_weight=self.config.audio_weight,
            visual_weight=self.config.visual_weight,
            content_weight=self.config.content_weight,
            engagement_weight=self.config.engagement_weight,
            quality_threshold=self.config.quality_threshold
        )
        
        # Create pipeline
        return HighlightPipeline([
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
        Process a video to OpusClip quality level.
        
        Args:
            video_path: Path to the input video
            transcription: Optional pre-existing transcription
            output_dir: Optional output directory for processed files
            
        Returns:
            Processing results with highlights and metadata
        """
        try:
            # Initialize context
            context = Context(
                video_path=video_path,
                metadata={
                    'processing_config': self.config.to_dict(),
                    'pipeline_version': 'opus_clip_level_v1'
                }
            )
            
            # Add transcription if provided
            if transcription:
                context.transcription = transcription
            
            # Pre-analyze video with all modalities
            logger.info("Starting comprehensive video analysis...")
            await self._comprehensive_video_analysis(context)
            
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
            raise
    
    async def _comprehensive_video_analysis(self, context: Context):
        """Run comprehensive analysis across all modalities."""
        # Initialize analyzers
        analyzers = {
            'audio': get_analyzer('audio', sample_rate=16000),
            'visual': get_analyzer('visual', frame_rate=2.0),
            'content': get_analyzer('content')
        }
        
        # Initialize all analyzers
        for analyzer in analyzers.values():
            await analyzer.initialize()
        
        try:
            # Run audio analysis
            logger.info("Analyzing audio features...")
            audio_result = await analyzers['audio'].analyze(Path(context.video_path))
            context.audio_analysis = audio_result.features
            
            # Run visual analysis
            logger.info("Analyzing visual features...")
            visual_result = await analyzers['visual'].analyze(Path(context.video_path))
            context.visual_analysis = visual_result.features
            
            # Run content analysis if transcription available
            if hasattr(context, 'transcription') and context.transcription:
                logger.info("Analyzing content features...")
                # Combine transcription text
                full_text = ' '.join(seg.get('text', '') for seg in context.transcription)
                content_result = await analyzers['content'].analyze(
                    Path(context.video_path),
                    transcript=full_text
                )
                context.content_analysis = content_result.features
            
            # Get video duration
            context.duration = self._get_video_duration(context.video_path)
            
            logger.info("Comprehensive analysis complete")
            
        finally:
            # Cleanup analyzers
            for analyzer in analyzers.values():
                await analyzer.cleanup()
    
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
            return 0.0
    
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
                    'annotations': getattr(s, 'annotations', {})
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
            },
            
            # Analysis metadata
            'analysis_metadata': {
                'audio_features_count': len(context.audio_analysis) if hasattr(context, 'audio_analysis') else 0,
                'visual_features_count': len(context.visual_analysis) if hasattr(context, 'visual_analysis') else 0,
                'content_features_count': len(context.content_analysis) if hasattr(context, 'content_analysis') else 0,
                'scene_changes': len(getattr(context, 'scene_changes', [])),
                'silence_sections': len(getattr(context, 'silence_sections', []))
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
        
        # Save highlights summary
        highlights_file = output_path / 'highlights_summary.json'
        highlights_data = {
            'highlights': results['highlights'],
            'quality_metrics': results['quality_metrics'],
            'config': results['processing_config']
        }
        with open(highlights_file, 'w') as f:
            json.dump(highlights_data, f, indent=2)
        
        logger.info(f"Results saved to {output_dir}")

# Convenience functions for easy usage

def create_opus_clip_config(
    content_type: str = 'general',
    target_duration: float = 60.0,
    quality_level: str = 'high'
) -> OpusClipConfig:
    """
    Create an OpusClip configuration optimized for specific content.
    
    Args:
        content_type: 'tutorial', 'interview', 'presentation', 'vlog', 'general'
        target_duration: Target total duration for highlights
        quality_level: 'standard', 'high', 'premium'
        
    Returns:
        Optimized configuration
    """
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
    """
    Process a video to OpusClip quality with simplified interface.
    
    Args:
        video_path: Path to the input video
        transcription: Optional transcription data
        content_type: Type of content for optimization
        target_duration: Target duration for highlights
        quality_level: Quality level setting
        output_dir: Optional output directory
        
    Returns:
        Processing results
    """
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

# Example usage
async def main():
    """Example usage of the OpusClip-level pipeline."""
    video_path = "path/to/your/video.mp4"
    
    # Option 1: Simple usage with automatic optimization
    results = await process_video_opus_clip_quality(
        video_path=video_path,
        content_type='tutorial',
        target_duration=90.0,
        quality_level='premium'
    )
    
    # Option 2: Advanced usage with custom configuration
    custom_config = OpusClipConfig(
        min_segment_duration=5.0,
        max_segment_duration=20.0,
        target_total_duration=120.0,
        quality_threshold=0.6,
        audio_weight=0.3,
        visual_weight=0.4,
        content_weight=0.2,
        engagement_weight=0.1
    )
    
    advanced_pipeline = OpusClipLevelPipeline(custom_config)
    advanced_results = await advanced_pipeline.process_video_to_opus_clip_quality(
        video_path=video_path,
        output_dir="output/"
    )
    
    print(f"Generated {len(results['highlights'])} high-quality highlights")
    print(f"Total duration: {results['quality_metrics']['total_highlight_duration']:.1f}s")
    print(f"Average score: {results['quality_metrics']['avg_highlight_score']:.3f}")
    
    # Print top highlights
    for i, highlight in enumerate(results['highlights'][:3], 1):
        print(f"\nHighlight {i}:")
        print(f"  Time: {highlight['start']:.1f}s - {highlight['end']:.1f}s")
        print(f"  Score: {highlight['score']:.3f}")
        print(f"  Text: {highlight['text'][:100]}...")

# Alias for backward compatibility
IntelligentSegmenter = OpusClipLevelPipeline

if __name__ == "__main__":
    asyncio.run(main())