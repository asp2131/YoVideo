"""
Visual feature analyzer for video content.

This module provides visual analysis capabilities including:
- Scene change detection
- Motion analysis
- Face detection
- Aesthetic quality assessment
"""
import cv2
import numpy as np
import logging
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import tempfile
import subprocess

from .base import BaseAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)

class VisualAnalyzer(BaseAnalyzer):
    """Analyzes visual features from video content."""
    
    def __init__(self, frame_rate: float = 1.0, **kwargs):
        """
        Initialize the visual analyzer.
        
        Args:
            frame_rate: Frames per second to sample for analysis
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.frame_rate = frame_rate
        self._temp_dir = None
        self._face_cascade = None
    
    @property
    def name(self) -> str:
        return "visual_analyzer"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self) -> None:
        """Initialize the analyzer and load required models."""
        await super().initialize()
        self._temp_dir = tempfile.TemporaryDirectory()
        try:
            # Try to load the face detection model
            self._face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
        except Exception as e:
            logger.warning(f"Could not load face detection model: {e}")
    
    async def cleanup(self) -> None:
        """Clean up temporary files and resources."""
        if self._temp_dir:
            self._temp_dir.cleanup()
        self._face_cascade = None
        await super().cleanup()
    
    async def analyze(self, video_path: Path, **kwargs) -> AnalysisResult:
        """
        Analyze visual features from the video.
        
        Args:
            video_path: Path to the video file
            **kwargs: Additional parameters
            
        Returns:
            AnalysisResult with visual features
        """
        try:
            # Extract frames for analysis
            frames_dir = await self._extract_frames(video_path)
            
            # Process frames
            features = await self._analyze_frames(frames_dir)
            
            return AnalysisResult(
                features=features,
                metadata={
                    'frame_rate': self.frame_rate,
                    'analyzer': self.name,
                    'analyzer_version': self.version
                }
            )
            
        except Exception as e:
            logger.error(f"Visual analysis failed: {str(e)}", exc_info=True)
            return AnalysisResult(success=False, error=str(e))
    
    async def _extract_frames(self, video_path: Path) -> Path:
        """Extract frames from video at specified frame rate."""
        if not self._temp_dir:
            raise RuntimeError("Analyzer not initialized")
            
        frames_dir = Path(self._temp_dir.name) / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        output_pattern = str(frames_dir / "frame_%04d.jpg")
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', f'fps={self.frame_rate}',
            '-q:v', '2',  # Quality level (2-31, lower is better)
            '-y',  # Overwrite output files
            output_pattern
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return frames_dir
        except subprocess.CalledProcessError as e:
            logger.error(f"Frame extraction failed: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to extract frames: {e.stderr.decode()}")
    
    async def _analyze_frames(self, frames_dir: Path) -> Dict[str, Any]:
        """Analyze extracted frames for visual features."""
        frame_files = sorted(frames_dir.glob("*.jpg"))
        if not frame_files:
            raise ValueError("No frames found for analysis")
        
        features = {
            'brightness': [],
            'contrast': [],
            'sharpness': [],
            'colorfulness': [],
            'face_count': [],
            'motion_energy': []
        }
        
        prev_frame = None
        
        for i, frame_file in enumerate(frame_files):
            # Load frame
            frame = cv2.imread(str(frame_file))
            if frame is None:
                continue
                
            # Convert to grayscale for some analyses
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Basic image statistics
            features['brightness'].append(np.mean(gray))
            features['contrast'].append(np.std(gray))
            
            # Sharpness (using Laplacian variance)
            features['sharpness'].append(cv2.Laplacian(gray, cv2.CV_64F).var())
            
            # Colorfulness (from colorfulness metric)
            if len(frame.shape) == 3:  # Color image
                b, g, r = cv2.split(frame.astype('float'))
                rg = np.abs(r - g)
                yb = np.abs(0.5 * (r + g) - b)
                features['colorfulness'].append((np.mean(rg) + np.mean(yb)) / 2)
            
            # Face detection
            if self._face_cascade is not None:
                faces = self._face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=1.1, 
                    minNeighbors=5, 
                    minSize=(30, 30)
                )
                features['face_count'].append(len(faces))
            
            # Motion detection (compare with previous frame)
            if prev_frame is not None:
                # Calculate absolute difference
                if prev_frame.shape == gray.shape:
                    diff = cv2.absdiff(prev_frame, gray)
                    motion = np.mean(diff)
                    features['motion_energy'].append(motion)
            
            prev_frame = gray
        
        # Aggregate features across frames
        result = {}
        for key, values in features.items():
            if values:  # Only process if we have values
                result[f'{key}_mean'] = float(np.mean(values))
                result[f'{key}_std'] = float(np.std(values)) if len(values) > 1 else 0.0
                result[f'{key}_max'] = float(np.max(values)) if values else 0.0
        
        return result
