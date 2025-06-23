"""
Base classes for video analysis plugins.

This module defines the base interfaces for all analyzer plugins.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

@dataclass
class AnalysisResult:
    """Container for analysis results from an analyzer."""
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

class BaseAnalyzer(ABC):
    """Base class for all analyzers."""
    
    def __init__(self, **config):
        """Initialize the analyzer with optional configuration."""
        self.config = config
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name identifier for this analyzer."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Return the version of this analyzer."""
        return "1.0.0"
    
    @abstractmethod
    async def analyze(self, video_path: Path, **kwargs) -> AnalysisResult:
        """
        Analyze the video and return features.
        
        Args:
            video_path: Path to the video file
            **kwargs: Additional analysis parameters
            
        Returns:
            AnalysisResult containing features and metadata
        """
        pass
    
    async def initialize(self) -> None:
        """Initialize any required resources for the analyzer."""
        if not self._initialized:
            self._initialized = True
    
    async def cleanup(self) -> None:
        """Clean up any resources used by the analyzer."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
