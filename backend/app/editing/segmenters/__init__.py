"""
Segmenters package for intelligent content-aware video segmentation.

This package contains implementations of different segmentation strategies
for creating meaningful video segments based on content analysis.
"""

# Import segmenter implementations here
from .intelligent_segmenter import OpusClipLevelPipeline as IntelligentSegmenter  # noqa

__all__ = ['IntelligentSegmenter']
