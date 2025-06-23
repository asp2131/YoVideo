"""
Unit tests for the video highlight pipeline integration.

These tests verify that the pipeline components work together correctly
without requiring actual video processing.
"""
import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.editing.pipeline.core import Context, Segment
from app.editing.pipeline.default_pipeline import create_default_pipeline


class TestPipelineIntegration:
    """Integration tests for the video highlight pipeline."""
    
    @pytest.fixture
    def mock_video_context(self, tmp_path):
        """Create a mock video processing context."""
        return Context(
            video_path="test_video.mp4",
            output_dir=str(tmp_path),
            duration=300,  # 5 minute video
            metadata={
                'original_filename': 'test_video.mp4',
                'processing_config': {}
            }
        )
    
    @pytest.fixture
    def mock_transcription(self):
        """Create a mock transcription result."""
        return {
            'segments': [
                {'start': 0, 'end': 5, 'text': 'This is a test segment'},
                {'start': 10, 'end': 15, 'text': 'Another test segment'},
                {'start': 20, 'end': 25, 'text': 'Yet another test segment'},
            ]
        }
    
    @pytest.fixture
    def mock_audio_analysis(self):
        """Create mock audio analysis results."""
        return {
            'silence_sections': [
                {'start': 5, 'end': 10},
                {'start': 15, 'end': 20}
            ],
            'audio_energy': [0.8, 0.9, 0.7]
        }
    
    @pytest.fixture
    def mock_video_analysis(self):
        """Create mock video analysis results."""
        return {
            'scene_changes': [0, 10, 20],
            'motion_vectors': [0.1, 0.5, 0.3],
            'face_detections': [
                {'start': 0, 'end': 5, 'count': 1},
                {'start': 10, 'end': 15, 'count': 2}
            ]
        }
    
    def test_pipeline_with_mock_data(self, mock_video_context, mock_transcription, 
                                   mock_audio_analysis, mock_video_analysis):
        """Test the pipeline with mock data processing."""
        # Create a test pipeline with mock processors
        pipeline = create_default_pipeline(
            min_highlight_duration=2.0,
            max_highlight_duration=15.0,
            target_total_duration=30.0
        )
        
        # Add mock data to context
        context = mock_video_context
        context.transcription = mock_transcription
        context.audio_analysis = mock_audio_analysis
        context.video_analysis = mock_video_analysis
        
        # Run the pipeline
        result_context = pipeline.run(context)
        
        # Verify results
        assert hasattr(result_context, 'segments'), "Segments should be created"
        assert hasattr(result_context, 'highlights'), "Highlights should be selected"
        
        # Verify segments were created from transcription
        assert len(result_context.segments) > 0, "Should create at least one segment"
        
        # Verify highlights were selected
        assert len(result_context.highlights) > 0, "Should select at least one highlight"
        
        # Verify highlight durations are within bounds
        for highlight in result_context.highlights:
            duration = highlight['end'] - highlight['start']
            assert duration >= 2.0, f"Highlight too short: {duration}"
            assert duration <= 15.0, f"Highlight too long: {duration}"
        
        # Verify total duration doesn't exceed target
        total_duration = sum(
            h['end'] - h['start'] 
            for h in result_context.highlights
        )
        assert total_duration <= 35.0, f"Total duration {total_duration}s exceeds target"
        
        # Verify metadata was updated
        assert 'highlight_selection' in result_context.metadata
        assert 'total_duration' in result_context.metadata['highlight_selection']
        assert 'segment_count' in result_context.metadata['highlight_selection']
        
        print("\nPipeline test passed with highlights:")
        for i, h in enumerate(result_context.highlights, 1):
            print(f"{i}. {h['start']:.1f}s - {h['end']:.1f}s "
                 f"(score: {h.get('score', 0):.2f})")


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])
