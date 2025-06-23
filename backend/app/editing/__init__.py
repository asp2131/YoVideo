"""
Video editing module for automatic video processing.

This module provides a flexible and extensible framework for processing videos
with both basic and advanced editing capabilities, including intelligent
content-aware segmentation and multi-modal analysis.
"""

from .core.processor import VideoProcessor, ProcessingPipeline, VideoEditingError
from .factory import (
    ProcessorFactory,
    EnhancedProcessorFactory,
    get_default_pipeline,
    get_legacy_pipeline,
    create_enhanced_pipeline_for_project
)
from .registry import PROCESSOR_REGISTRY, register_processor, get_processor_class

# Import processors to register them
from .processors import (  # noqa
    silence_remover,
    scene_detector,
    enhanced_highlight_detector,
)
from .segmenters import intelligent_segmenter  # noqa

__all__ = [
    # Core components
    'VideoProcessor',
    'ProcessingPipeline',
    'VideoEditingError',
    
    # Factories
    'ProcessorFactory',
    'EnhancedProcessorFactory',
    
    # Pipeline creators
    'get_default_pipeline',
    'get_legacy_pipeline',
    'create_enhanced_pipeline_for_project',
    
    # Registry
    'PROCESSOR_REGISTRY',
    'register_processor',
    'get_processor_class',
]