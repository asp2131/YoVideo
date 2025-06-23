"""
Tests for the EnhancedHighlightDetector class.

This module contains unit tests for the multi-modal highlight detection functionality.
"""
import os
import sys
import json
import logging
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to the path to allow imports
sys.path.append(str(Path(__file__).parent.parent))

from app.editing.processors.highlight_detector import HighlightDetector

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestEnhancedHighlightDetector(unittest.TestCase):
    """Test cases for the EnhancedHighlightDetector."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_video = Path("test_data/test_video.mp4")
        self.test_audio = Path("test_data/test_audio.wav")
        self.test_transcription = [
            {"text": "This is a test video about gardening.", "start": 0.0, "end": 3.5, "duration": 3.5},
            {"text": "Look at these beautiful tomato plants!", "start": 4.0, "end": 7.0, "duration": 3.0},
            {"text": "They're growing so well in this soil.", "start": 7.5, "end": 10.0, "duration": 2.5},
            {"text": "Let me show you how to prune them.", "start": 10.5, "end": 13.0, "duration": 2.5},
            {"text": "First, identify the main stem and look for suckers.", "start": 13.5, "end": 17.0, "duration": 3.5},
            {"text": "Carefully remove them to improve air flow.", "start": 17.5, "end": 20.0, "duration": 2.5},
            {"text": "This will help prevent diseases and improve yield.", "start": 20.5, "end": 24.0, "duration": 3.5},
            {"text": "Thanks for watching! Don't forget to like and subscribe.", "start": 24.5, "end": 28.0, "duration": 3.5}
        ]
        
        # Create test data directory if it doesn't exist
        self.test_data_dir = Path("test_data")
        self.test_data_dir.mkdir(exist_ok=True)
        
        # Initialize the detector with test-friendly parameters
        self.detector = HighlightDetector(
            min_duration=2.0,
            max_duration=10.0,
            min_highlight_duration=15,
            always_include_first=5,
            analysis_interval=1.0  # Faster for testing
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up any test files if needed
        pass
    
    @patch('cv2.VideoCapture')
    @patch('librosa.load')
    def test_analyze_audio(self, mock_load, mock_video_capture):
        """Test audio analysis functionality."""
        # Mock librosa.load to return test audio data
        mock_load.return_value = (np.random.rand(16000 * 30), 16000)  # 30s of audio at 16kHz
        
        # Call the method
        audio_features = self.detector._analyze_audio(self.test_video)
        
        # Verify basic structure of the results
        self.assertIn('energy_peaks', audio_features)
        self.assertIn('rms_energy', audio_features)
        self.assertIn('speech_segments', audio_features)
        self.assertIn('duration', audio_features)
        
        # Verify the duration is approximately what we'd expect
        self.assertAlmostEqual(audio_features['duration'], 30.0, delta=0.1)
    
    @patch('cv2.VideoCapture')
    def test_analyze_visual(self, mock_video_capture):
        """Test visual analysis functionality."""
        # Mock cv2.VideoCapture to return test frames
        mock_cap = MagicMock()
        mock_cap.get.side_effect = [30.0, 1280, 720, 25.0, 300]  # fps, width, height, total_frames, duration
        
        # Mock frame reading
        mock_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_video_capture.return_value = mock_cap
        
        # Call the method
        visual_features = self.detector._analyze_visual(self.test_video)
        
        # Verify basic structure of the results
        self.assertIn('scene_changes', visual_features)
        self.assertIn('motion_scores', visual_features)
        self.assertIn('face_detections', visual_features)
        self.assertIn('plant_frames', visual_features)
        self.assertIn('duration', visual_features)
    
    def test_analyze_content(self):
        """Test content analysis functionality."""
        # Call the method with test transcription
        content_features = self.detector._analyze_content(self.test_transcription)
        
        # Verify basic structure of the results
        self.assertIn('keywords', content_features)
        self.assertIn('sentiment_scores', content_features)
        self.assertIn('speaking_rates', content_features)
        self.assertIn('emphasis_moments', content_features)
        
        # Verify some expected keywords were found
        keywords = [k['keyword'] for k in content_features['keywords']]
        self.assertIn('tomato', ' '.join(keywords).lower())
        self.assertIn('prune', ' '.join(keywords).lower())
    
    def test_score_segments(self):
        """Test segment scoring functionality."""
        # Create test segments
        segments = [
            {'start': 0.0, 'end': 5.0, 'type': 'initial'},
            {'start': 10.0, 'end': 20.0, 'type': 'content'},
            {'start': 25.0, 'end': 30.0, 'type': 'conclusion'}
        ]
        
        # Create mock features
        audio_features = {
            'energy_peaks': [1.0, 2.0, 11.0, 12.0, 26.0, 27.0],
            'rms_energy': np.ones(1000) * 0.5,
            'times': np.linspace(0, 30, 1000),
            'speech_segments': [
                {'start': 0.0, 'end': 5.0, 'type': 'speech'},
                {'start': 10.0, 'end': 20.0, 'type': 'speech'},
                {'start': 25.0, 'end': 30.0, 'type': 'speech'}
            ]
        }
        
        visual_features = {
            'scene_changes': [10.0, 25.0],
            'motion_scores': [
                {'time': 1.0, 'score': 10.0},
                {'time': 11.0, 'score': 50.0},
                {'time': 26.0, 'score': 20.0}
            ],
            'face_detections': [
                {'time': 1.0, 'face_count': 1, 'largest_face_area': 10000},
                {'time': 11.0, 'face_count': 1, 'largest_face_area': 15000}
            ],
            'plant_frames': [
                {'time': 11.0, 'green_ratio': 0.3},
                {'time': 12.0, 'green_ratio': 0.4}
            ]
        }
        
        # Call the method
        scored_segments = self.detector._score_segments(
            segments, audio_features, visual_features, self.test_transcription
        )
        
        # Verify all segments have scores
        self.assertEqual(len(scored_segments), 3)
        for seg in scored_segments:
            self.assertIn('score', seg)
            self.assertGreaterEqual(seg['score'], 0.0)
            
        # The content segment should have the highest score
        scores = [s['score'] for s in scored_segments]
        self.assertEqual(scores[1], max(scores))
    
    def test_select_best_segments(self):
        """Test segment selection functionality."""
        # Create test segments with scores
        segments = [
            {'start': 0.0, 'end': 5.0, 'score': 0.5},
            {'start': 10.0, 'end': 20.0, 'score': 0.9},
            {'start': 25.0, 'end': 30.0, 'score': 0.7}
        ]
        
        # Call the method with a target duration that should include all segments
        selected = self.detector._select_best_segments(segments, target_duration=30.0)
        self.assertEqual(len(selected), 3)
        
        # Call with a target duration that should only include the highest scoring segment
        selected = self.detector._select_best_segments(segments, target_duration=15.0)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['start'], 10.0)  # Highest scoring segment
    
    @patch('cv2.VideoCapture')
    @patch('librosa.load')
    def test_process(self, mock_load, mock_video_capture):
        """Test the main process method."""
        # Mock dependencies
        mock_load.return_value = (np.random.rand(16000 * 30), 16000)
        
        mock_cap = MagicMock()
        mock_cap.get.side_effect = [30.0, 1280, 720, 25.0, 300]
        mock_cap.read.return_value = (True, np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap
        
        # Call the method
        result = self.detector.process(
            input_path=self.test_video,
            transcription=self.test_transcription
        )
        
        # Verify the result structure
        self.assertIn('status', result)
        self.assertEqual(result['status'], 'success')
        self.assertIn('segments', result)
        self.assertIn('total_duration', result)
        
        # Verify we got some segments
        self.assertGreater(len(result['segments']), 0)
        
        # Verify the first segment includes the required initial segment
        self.assertLessEqual(result['segments'][0]['end'], self.detector.always_include_first)


if __name__ == '__main__':
    unittest.main()
