"""
Audio feature analyzer for video content.

This module provides audio analysis capabilities including:
- Energy levels
- Speech/music detection
- Silence detection
- Speaker diarization (basic)
"""
import numpy as np
import librosa
import logging
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import tempfile
import subprocess

from .base import BaseAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)

class AudioAnalyzer(BaseAnalyzer):
    """Analyzes audio features from video content."""
    
    def __init__(self, sample_rate: int = 16000, **kwargs):
        """
        Initialize the audio analyzer.
        
        Args:
            sample_rate: Target sample rate for audio analysis
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.sample_rate = sample_rate
        self._temp_dir = None
    
    @property
    def name(self) -> str:
        return "audio_analyzer"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self) -> None:
        """Initialize the analyzer and create temporary directory."""
        await super().initialize()
        self._temp_dir = tempfile.TemporaryDirectory()
    
    async def cleanup(self) -> None:
        """Clean up temporary files."""
        if self._temp_dir:
            self._temp_dir.cleanup()
        await super().cleanup()
    
    async def analyze(self, video_path: Path, **kwargs) -> AnalysisResult:
        """
        Analyze audio features from the video.
        
        Args:
            video_path: Path to the video file
            **kwargs: Additional parameters
            
        Returns:
            AnalysisResult with audio features
        """
        try:
            # Extract audio from video
            audio_file = await self._extract_audio(video_path)
            
            # Load audio file
            y, sr = librosa.load(audio_file, sr=self.sample_rate)
            
            # Extract features
            features = await self._extract_features(y, sr)
            
            return AnalysisResult(
                features=features,
                metadata={
                    'sample_rate': sr,
                    'duration': len(y) / sr,
                    'analyzer': self.name,
                    'analyzer_version': self.version
                }
            )
            
        except Exception as e:
            logger.error(f"Audio analysis failed: {str(e)}", exc_info=True)
            return AnalysisResult(success=False, error=str(e))
    
    async def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video using ffmpeg."""
        if not self._temp_dir:
            raise RuntimeError("Analyzer not initialized")
            
        output_path = Path(self._temp_dir.name) / "audio.wav"
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vn',  # Disable video
            '-acodec', 'pcm_s16le',  # PCM 16-bit
            '-ar', str(self.sample_rate),
            '-ac', '1',  # Mono
            '-y',  # Overwrite output file if it exists
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Audio extraction failed: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to extract audio: {e.stderr.decode()}")
    
    async def _extract_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract audio features from the audio signal."""
        features = {}
        
        # Basic features
        features['rms_energy'] = float(np.sqrt(np.mean(y**2)))  # RMS energy
        features['zcr'] = float(np.mean(librosa.feature.zero_crossing_rate(y)[0]))  # Zero-crossing rate
        
        # Spectral features
        stft = np.abs(librosa.stft(y))
        features['spectral_centroid'] = float(np.mean(librosa.feature.spectral_centroid(S=stft, sr=sr)))
        features['spectral_bandwidth'] = float(np.mean(librosa.feature.spectral_bandwidth(S=stft, sr=sr)))
        
        # MFCCs (first 13 coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        for i, mfcc in enumerate(mfccs):
            features[f'mfcc_{i+1}_mean'] = float(np.mean(mfcc))
            features[f'mfcc_{i+1}_std'] = float(np.std(mfcc))
        
        # Silence detection
        frame_length = 2048
        hop_length = 512
        rms_energy = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        silence_threshold = np.percentile(rms_energy, 10)  # Bottom 10% as silence
        features['silence_ratio'] = float(np.mean(rms_energy < silence_threshold))
        
        # Speech/music classification (simplified)
        features['is_speech'] = self._classify_speech_music(y, sr)
        
        return features
    
    def _classify_speech_music(self, y: np.ndarray, sr: int) -> bool:
        """Simple speech/music classifier based on spectral features."""
        # This is a simplified version - in production, use a trained model
        stft = np.abs(librosa.stft(y))
        
        # Calculate features
        spectral_flatness = np.mean(librosa.feature.spectral_flatness(S=stft))
        zcr = np.mean(librosa.feature.zero_crossing_rate(y))
        
        # Simple heuristic: speech has higher zero-crossing rate and lower spectral flatness
        return zcr > 0.1 and spectral_flatness < 0.5
