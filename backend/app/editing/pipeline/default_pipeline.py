"""
Default pipeline configuration for video processing.

This module provides a pre-configured pipeline for processing videos through
the various analysis and segmentation stages.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any

from .core import HighlightPipeline, Context
from ..processors.silence_remover import SilenceRemover
from ..processors.scene_detector import SceneDetector
from ..segmenters.intelligent_segmenter import IntelligentSegmenter
from ..processors.enhanced_highlight_detector import EnhancedHighlightDetector


def create_default_pipeline(
    min_highlight_duration: float = 2.0,
    max_highlight_duration: float = 15.0,
    target_total_duration: float = 60.0,
    silence_threshold: float = -30.0,
    silence_min_duration: float = 0.5,
    scene_threshold: float = 30.0,
    min_scene_len: float = 1.5,
    use_scene_boundaries: bool = True,
    respect_silence: bool = True
) -> HighlightPipeline:
    """
    Create a default pipeline with recommended settings.
    
    Args:
        min_highlight_duration: Minimum duration of a highlight segment (seconds)
        max_highlight_duration: Maximum duration of a highlight segment (seconds)
        target_total_duration: Target total duration of all highlights (seconds)
        silence_threshold: Volume threshold in dB below which audio is considered silent
        silence_min_duration: Minimum duration of silence to be detected (seconds)
        scene_threshold: Threshold for scene change detection (lower = more sensitive)
        min_scene_len: Minimum length of a scene in seconds
        use_scene_boundaries: Whether to respect scene boundaries in segmentation
        respect_silence: Whether to avoid cutting in the middle of speech
        
    Returns:
        Configured HighlightPipeline instance
    """
    # Create processors with default settings
    silence_remover = SilenceRemover(
        silence_threshold=silence_threshold,
        silence_duration=silence_min_duration
    )
    
    scene_detector = SceneDetector(
        threshold=scene_threshold,
        min_scene_len=min_scene_len
    )
    
    segmenter = IntelligentSegmenter(
        min_segment_duration=min_highlight_duration,
        max_segment_duration=max_highlight_duration,
        use_scene_boundaries=use_scene_boundaries,
        respect_silence=respect_silence
    )
    
    highlight_detector = EnhancedHighlightDetector(
        min_duration=min_highlight_duration,
        max_duration=max_highlight_duration,
        target_total_duration=target_total_duration,
        audio_weight=0.4,
        visual_weight=0.3,
        content_weight=0.3,
        scene_change_bonus=0.2,
        silence_penalty=0.3,
        face_detection_enabled=True,
        motion_analysis_enabled=True,
        sentiment_analysis_enabled=True
    )
    
    # Assemble the pipeline
    pipeline = HighlightPipeline([
        silence_remover,
        scene_detector,
        segmenter,
        highlight_detector
    ])
    
    return pipeline


def process_video(
    video_path: str,
    output_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a video file using the default pipeline.
    
    Args:
        video_path: Path to the input video file
        output_dir: Directory to save output files (if None, uses video directory)
        config: Optional configuration overrides
        
    Returns:
        Dictionary containing processing results
    """
    # Apply config overrides or use defaults
    pipeline_config = {
        'min_highlight_duration': 2.0,
        'max_highlight_duration': 15.0,
        'target_total_duration': 60.0,
        'silence_threshold': -30.0,
        'silence_min_duration': 0.5,
        'scene_threshold': 30.0,
        'min_scene_len': 1.5,
        'use_scene_boundaries': True,
        'respect_silence': True
    }
    
    if config:
        pipeline_config.update(config)
    
    # Create output directory if needed
    video_path = Path(video_path).resolve()
    if output_dir is None:
        output_dir = video_path.parent
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize context
    context = Context(
        video_path=str(video_path),
        output_dir=str(output_dir),
        metadata={
            'original_filename': video_path.name,
            'processing_config': pipeline_config
        }
    )
    
    # Create and run pipeline
    pipeline = create_default_pipeline(**pipeline_config)
    context = pipeline.run(context)
    
    # Prepare results
    results = {
        'video_path': str(video_path),
        'output_dir': str(output_dir),
        'duration': getattr(context, 'duration', 0),
        'highlights': getattr(context, 'highlights', []),
        'segments': [
            {'start': s.start, 'end': s.end, 'text': getattr(s, 'text', '')} 
            for s in getattr(context, 'segments', [])
        ],
        'scene_changes': getattr(context, 'scene_changes', []),
        'silence_sections': getattr(context, 'silence_sections', []),
        'metadata': getattr(context, 'metadata', {})
    }
    
    return results
