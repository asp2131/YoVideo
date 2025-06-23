"""
Factory for creating and configuring video processors.

This module provides both basic and enhanced factory implementations for
creating video processing pipelines with different capabilities.
"""

from typing import Dict, Type, Any, Optional, List
import logging
from pathlib import Path

from .core.processor import VideoProcessor, ProcessingPipeline
from .registry import register_processor, get_processor_class

logger = logging.getLogger(__name__)

# Import and register all processors
from .processors.silence_remover import SilenceRemover
from .processors.scene_detector import SceneDetector
from .processors.highlight_detector import HighlightDetector
from .processors.enhanced_highlight_detector import EnhancedHighlightDetector
from .segmenters.intelligent_segmenter import IntelligentSegmenter

# Register all processors
register_processor('silence_remover', SilenceRemover)
register_processor('scene_detector', SceneDetector)
register_processor('highlight_detector', HighlightDetector)
register_processor('enhanced_highlight_detector', EnhancedHighlightDetector)
register_processor('intelligent_segmenter', IntelligentSegmenter)

class ProcessorFactory:
    """Factory for creating and configuring video processors."""
    
    @staticmethod
    def get_processor(processor_type: str, **kwargs) -> VideoProcessor:
        """
        Create a processor of the specified type.
        
        Args:
            processor_type: Type of processor to create
            **kwargs: Configuration parameters for the processor
            
        Returns:
            Configured processor instance
            
        Raises:
            ValueError: If the processor type is not recognized
        """
        processor_class = get_processor_class(processor_type)
        
        try:
            return processor_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating processor {processor_type}: {e}")
            raise
    
    @staticmethod
    def create_pipeline(processors_config: list) -> ProcessingPipeline:
        """
        Create a processing pipeline from a list of processor configurations.
        
        Args:
            processors_config: List of processor configurations, where each is a dict with
                             'type' and optional 'params'
            
        Returns:
            Configured ProcessingPipeline instance
        """
        pipeline = ProcessingPipeline()
        
        for config in processors_config:
            processor_type = config.get('type')
            if not processor_type:
                logger.warning("Processor config missing 'type' field, skipping")
                continue
                
            params = config.get('params', {})
            
            try:
                processor = ProcessorFactory.get_processor(processor_type, **params)
                pipeline.add_processor(processor)
                logger.info(f"Added processor: {processor.name}")
            except Exception as e:
                logger.error(f"Failed to add processor {processor_type}: {e}")
                raise
        
        return pipeline


class EnhancedProcessorFactory:
    """
    Enhanced factory for creating intelligent video processing pipelines
    with content-aware segmentation and multi-modal analysis.
    """
    
    @staticmethod
    def create_intelligent_editing_pipeline(
        editing_style: str = "engaging",
        target_duration: float = 60.0,
        content_type: str = "general"
    ) -> ProcessingPipeline:
        """
        Create an intelligent editing pipeline based on content type and style.
        
        Args:
            editing_style: "engaging", "professional", "educational", "social_media"
            target_duration: Target duration for final video in seconds
            content_type: "tutorial", "interview", "presentation", "vlog", "general"
            
        Returns:
            Configured ProcessingPipeline
        """
        pipeline = ProcessingPipeline()
        
        # Configure based on editing style and content type
        config = EnhancedProcessorFactory._get_style_config(editing_style, content_type)
        
        # Add intelligent segmenter
        segmenter = IntelligentSegmenter(
            min_segment_duration=config['min_segment_duration'],
            max_segment_duration=config['max_segment_duration'],
            semantic_threshold=config['semantic_threshold']
        )
        pipeline.add_processor(segmenter)
        
        # Add enhanced highlight detector
        highlight_detector = EnhancedHighlightDetector(
            min_duration=config['min_highlight_duration'],
            max_duration=config['max_highlight_duration'],
            target_total_duration=target_duration,
            audio_weight=config['audio_weight'],
            visual_weight=config['visual_weight'],
            content_weight=config['content_weight'],
            face_detection_enabled=config['face_detection'],
            motion_analysis_enabled=config['motion_analysis'],
            sentiment_analysis_enabled=config['sentiment_analysis']
        )
        pipeline.add_processor(highlight_detector)
        
        logger.info(f"Created {editing_style} pipeline for {content_type} content")
        return pipeline
    
    @staticmethod
    def _get_style_config(editing_style: str, content_type: str) -> Dict[str, Any]:
        """
        Get configuration parameters based on editing style and content type.
        """
        base_configs = {
            "engaging": {
                'min_segment_duration': 3.0,
                'max_segment_duration': 15.0,
                'min_highlight_duration': 2.0,
                'max_highlight_duration': 12.0,
                'semantic_threshold': 0.4,
                'audio_weight': 0.4,
                'visual_weight': 0.3,
                'content_weight': 0.3,
                'face_detection': True,
                'motion_analysis': True,
                'sentiment_analysis': True
            },
            "professional": {
                'min_segment_duration': 5.0,
                'max_segment_duration': 25.0,
                'min_highlight_duration': 4.0,
                'max_highlight_duration': 20.0,
                'semantic_threshold': 0.3,
                'audio_weight': 0.2,
                'visual_weight': 0.2,
                'content_weight': 0.6,
                'face_detection': True,
                'motion_analysis': False,
                'sentiment_analysis': True
            },
            "educational": {
                'min_segment_duration': 8.0,
                'max_segment_duration': 30.0,
                'min_highlight_duration': 6.0,
                'max_highlight_duration': 25.0,
                'semantic_threshold': 0.25,
                'audio_weight': 0.3,
                'visual_weight': 0.2,
                'content_weight': 0.5,
                'face_detection': True,
                'motion_analysis': False,
                'sentiment_analysis': False
            },
            "social_media": {
                'min_segment_duration': 2.0,
                'max_segment_duration': 10.0,
                'min_highlight_duration': 1.5,
                'max_highlight_duration': 8.0,
                'semantic_threshold': 0.5,
                'audio_weight': 0.5,
                'visual_weight': 0.4,
                'content_weight': 0.1,
                'face_detection': True,
                'motion_analysis': True,
                'sentiment_analysis': True
            }
        }
        
        config = base_configs.get(editing_style, base_configs["engaging"])
        
        # Adjust based on content type
        content_adjustments = {
            "tutorial": {
                'semantic_threshold': 0.2,  # More sensitive to topic changes
                'content_weight': 0.6,      # Focus more on content
                'min_segment_duration': config['min_segment_duration'] * 1.5
            },
            "interview": {
                'face_detection': True,      # Important for interviews
                'audio_weight': 0.4,         # Focus on audio changes (speaker changes)
                'semantic_threshold': 0.35
            },
            "presentation": {
                'visual_weight': 0.4,        # Slides changes are important
                'motion_analysis': False,    # Less motion in presentations
                'min_segment_duration': config['min_segment_duration'] * 1.2
            },
            "vlog": {
                'sentiment_analysis': True,  # Personal content benefits from sentiment
                'face_detection': True,      # Face-to-camera content
                'audio_weight': 0.3,
                'content_weight': 0.4
            }
        }
        
        if content_type in content_adjustments:
            config.update(content_adjustments[content_type])
        
        return config


def create_enhanced_pipeline_for_project(
    project_id: str,
    transcription: Optional[List[Dict]] = None,
    editing_preferences: Optional[Dict] = None
) -> ProcessingPipeline:
    """
    Create a customized pipeline for a specific project.
    
    Args:
        project_id: Project identifier
        transcription: Transcription data for content analysis
        editing_preferences: User preferences for editing style
        
    Returns:
        Customized ProcessingPipeline
    """
    # Default preferences
    preferences = {
        'style': 'engaging',
        'target_duration': 60.0,
        'content_type': 'general',
        'preserve_speech': True,
        'enhance_audio': True,
        'detect_faces': True
    }
    
    if editing_preferences:
        preferences.update(editing_preferences)
    
    # Auto-detect content type if transcription is available
    if transcription and preferences['content_type'] == 'general':
        detected_type = _detect_content_type(transcription)
        if detected_type:
            preferences['content_type'] = detected_type
            logger.info(f"Auto-detected content type: {detected_type}")
    
    # Create pipeline
    pipeline = EnhancedProcessorFactory.create_intelligent_editing_pipeline(
        editing_style=preferences['style'],
        target_duration=preferences['target_duration'],
        content_type=preferences['content_type']
    )
    
    return pipeline


def _detect_content_type(transcription: List[Dict]) -> Optional[str]:
    """
    Auto-detect content type from transcription.
    """
    if not transcription:
        return None
    
    # Combine all text
    full_text = ' '.join(seg.get('text', '') for seg in transcription).lower()
    
    # Tutorial indicators
    tutorial_keywords = [
        'how to', 'step', 'first', 'next', 'then', 'tutorial', 'guide',
        'learn', 'teach', 'show you', 'demonstrate', 'example'
    ]
    
    # Interview indicators  
    interview_keywords = [
        'interview', 'question', 'answer', 'tell me', 'what do you think',
        'your opinion', 'experience', 'background', 'career'
    ]
    
    # Presentation indicators
    presentation_keywords = [
        'presentation', 'slide', 'agenda', 'overview', 'summary',
        'conclusion', 'data shows', 'research', 'study', 'analysis'
    ]
    
    # Vlog indicators
    vlog_keywords = [
        'today', 'yesterday', 'my day', 'personal', 'life', 'feeling',
        'excited', 'update', 'sharing', 'experience', 'story'
    ]
    
    # Count keyword occurrences
    keyword_counts = {
        'tutorial': sum(1 for keyword in tutorial_keywords if keyword in full_text),
        'interview': sum(1 for keyword in interview_keywords if keyword in full_text),
        'presentation': sum(1 for keyword in presentation_keywords if keyword in full_text),
        'vlog': sum(1 for keyword in vlog_keywords if keyword in full_text)
    }
    
    # Return type with highest count (if above threshold)
    max_count = max(keyword_counts.values())
    if max_count >= 2:  # At least 2 keyword matches
        return max(keyword_counts, key=keyword_counts.get)
    
    return None


def get_default_pipeline(target_duration: float = 60.0) -> ProcessingPipeline:
    """
    Get a default processing pipeline with commonly used processors.
    
    Args:
        target_duration: Target duration for highlights in seconds
        
    Returns:
        Configured ProcessingPipeline instance
    """
    # Use the enhanced pipeline by default
    return EnhancedProcessorFactory.create_intelligent_editing_pipeline(
        editing_style="engaging",
        target_duration=target_duration,
        content_type="general"
    )


def get_legacy_pipeline() -> ProcessingPipeline:
    """
    Get the legacy processing pipeline (for backward compatibility).
    
    Returns:
        Configured ProcessingPipeline instance with basic processors
    """
    processors_config = [
        {
            'type': 'scene_detector',
            'params': {
                'threshold': 30.0,
                'min_scene_len': 1.5
            }
        },
        {
            'type': 'highlight_detector',
            'params': {
                'min_duration': 3.0,
                'max_duration': 15.0,
                'min_silence_len': 300,  # ms
                'silence_thresh': -40,    # dB
                'keep_silence': 200       # ms
            }
        },
        {
            'type': 'silence_remover',
            'params': {
                'silence_threshold': -30.0,
                'silence_duration': 0.5
            }
        }
    ]
    
    return ProcessorFactory.create_pipeline(processors_config)
