"""
Video analysis plugins for extracting features from video content.

This package provides a set of analyzers that can extract various features
from video content, including audio, visual, and text-based features.

Available analyzers:
- AudioAnalyzer: Extracts audio features like energy, pitch, and speech/music detection
- VisualAnalyzer: Extracts visual features like scene changes, motion, and faces
- ContentAnalyzer: Analyzes text content from subtitles/transcripts
"""
from typing import Dict, Type, Any, Optional
import importlib
import logging
from pathlib import Path

from .base import BaseAnalyzer, AnalysisResult
from .audio_analyzer import AudioAnalyzer
from .visual_analyzer import VisualAnalyzer
from .content_analyzer import ContentAnalyzer

# Export main classes
__all__ = [
    'BaseAnalyzer',
    'AnalysisResult',
    'AudioAnalyzer',
    'VisualAnalyzer',
    'ContentAnalyzer',
    'get_analyzer',
    'get_available_analyzers'
]

# Default analyzers that come with the package
DEFAULT_ANALYZERS = {
    'audio': AudioAnalyzer,
    'visual': VisualAnalyzer,
    'content': ContentAnalyzer,
}

# Cache for dynamically loaded analyzers
_analyzer_cache: Dict[str, Type[BaseAnalyzer]] = {}

def get_available_analyzers() -> Dict[str, Type[BaseAnalyzer]]:
    """
    Get all available analyzers, including both built-in and dynamically loaded ones.
    
    Returns:
        Dictionary mapping analyzer names to their classes
    """
    return {**DEFAULT_ANALYZERS, **_analyzer_cache}

def get_analyzer(name: str, **kwargs) -> BaseAnalyzer:
    """
    Get an analyzer instance by name.
    
    Args:
        name: Name of the analyzer (e.g., 'audio', 'visual')
        **kwargs: Additional arguments to pass to the analyzer constructor
        
    Returns:
        An instance of the requested analyzer
        
    Raises:
        ValueError: If the analyzer is not found
    """
    # Check built-in analyzers first
    if name in DEFAULT_ANALYZERS:
        return DEFAULT_ANALYZERS[name](**kwargs)
    
    # Check dynamically loaded analyzers
    if name in _analyzer_cache:
        return _analyzer_cache[name](**kwargs)
    
    # Try to load from plugins
    try:
        module_name = f"app.editing.analyzers.plugins.{name}"
        module = importlib.import_module(module_name)
        analyzer_class = getattr(module, f"{name.capitalize()}Analyzer", None)
        
        if analyzer_class and issubclass(analyzer_class, BaseAnalyzer):
            _analyzer_cache[name] = analyzer_class
            return analyzer_class(**kwargs)
    except ImportError:
        pass
    
    raise ValueError(f"Unknown analyzer: {name}")

def register_analyzer(name: str, analyzer_class: Type[BaseAnalyzer]) -> None:
    """
    Register a custom analyzer class.
    
    Args:
        name: Name to register the analyzer under
        analyzer_class: Analyzer class to register
        
    Raises:
        TypeError: If analyzer_class is not a subclass of BaseAnalyzer
    """
    if not issubclass(analyzer_class, BaseAnalyzer):
        raise TypeError("Analyzer must be a subclass of BaseAnalyzer")
    _analyzer_cache[name] = analyzer_class

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
