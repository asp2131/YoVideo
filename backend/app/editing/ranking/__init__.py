"""
Video segment ranking module.

This module provides functionality for learning to rank video segments
based on their predicted interestingness or highlight potential.

Key Components:
- FeatureExtractor: Extracts features from video segments
- BaseRankingModel: Abstract base class for ranking models
- RandomForestRankingModel: Implementation using Random Forest
- get_model: Factory function to create ranking models
"""
from typing import Dict, Any, Type, Optional
import logging

from .feature_extractor import FeatureExtractor
from .model import (
    BaseRankingModel,
    RandomForestRankingModel,
    get_model
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Export public API
__all__ = [
    'FeatureExtractor',
    'BaseRankingModel',
    'RandomForestRankingModel',
    'get_model',
]
