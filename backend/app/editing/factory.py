"""Factory for creating and configuring video processors."""
from typing import Dict, Type, Any, Optional
import logging
from pathlib import Path

from .core.processor import VideoProcessor, ProcessingPipeline
from .registry import register_processor, get_processor_class

logger = logging.getLogger(__name__)

# Import processors to register them
from .processors.silence_remover import SilenceRemover
from .processors.scene_detector import SceneDetector
from .processors.highlight_detector import HighlightDetector

# Register default processors
register_processor('silence_remover', SilenceRemover)
register_processor('scene_detector', SceneDetector)
register_processor('highlight_detector', HighlightDetector)

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


def get_default_pipeline() -> ProcessingPipeline:
    """
    Get a default processing pipeline with commonly used processors.
    
    Returns:
        Configured ProcessingPipeline instance
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
