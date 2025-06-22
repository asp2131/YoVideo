"""
Registry for video processor classes.
This module contains the processor registry to avoid circular imports.
"""
from typing import Dict, Type
from .core.processor import VideoProcessor

# Registry of available processors
PROCESSOR_REGISTRY: Dict[str, Type[VideoProcessor]] = {}

def register_processor(name: str, processor_class: Type[VideoProcessor]) -> None:
    """
    Register a processor class with the given name.
    
    Args:
        name: The name to register the processor under
        processor_class: The processor class to register
    """
    PROCESSOR_REGISTRY[name] = processor_class

def get_processor_class(name: str) -> Type[VideoProcessor]:
    """
    Get a processor class by name.
    
    Args:
        name: The name of the processor to get
        
    Returns:
        The processor class
        
    Raises:
        ValueError: If the processor is not found
    """
    processor_class = PROCESSOR_REGISTRY.get(name.lower())
    if not processor_class:
        raise ValueError(f"Unknown processor type: {name}")
    return processor_class
