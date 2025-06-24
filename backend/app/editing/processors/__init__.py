"""
Video processing modules for the editing pipeline.

This package contains various processors that can be used in the video editing pipeline.
Each processor implements the VideoProcessor interface and performs a specific task.
"""

from .scene_detector import SceneDetector
from .silence_remover import SilenceRemover
from .enhanced_highlight_detector import EnhancedHighlightDetector, HighlightScore
from .highlight_detector import HighlightDetector
from .diversity_processor import DiversityProcessor

__all__ = [
    'SceneDetector',
    'SilenceRemover',
    'EnhancedHighlightDetector',
    'HighlightScore',
    'HighlightDetector',
    'DiversityProcessor',
]
