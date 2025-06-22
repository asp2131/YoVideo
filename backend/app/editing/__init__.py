"""Video editing module for automatic video processing."""

from .core.processor import VideoProcessor, ProcessingPipeline, VideoEditingError
from .factory import ProcessorFactory, get_default_pipeline
from .registry import PROCESSOR_REGISTRY, register_processor, get_processor_class

# Import processors to register them
from .processors import silence_remover, scene_detector  # noqa

__all__ = [
    'VideoProcessor',
    'ProcessingPipeline',
    'VideoEditingError',
    'ProcessorFactory',
    'get_default_pipeline',
    'PROCESSOR_REGISTRY',
    'register_processor',
    'get_processor_class',
]