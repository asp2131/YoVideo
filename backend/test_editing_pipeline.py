#!/usr/bin/env python3
"""
Test script for the video editing pipeline.
This script tests the integration of the HighlightDetector with the processing pipeline.
"""
import unittest
import tempfile
import shutil
import os
import json
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
import sys
sys.path.append(str(Path(__file__).parent))

from app.editing.factory import get_default_pipeline
from app.editing.utils.video_utils import get_video_info

class TestEditingPipeline(unittest.TestCase):
    """Test cases for the video editing pipeline."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before any tests are run."""
        # Create a temporary directory for test outputs
        cls.test_dir = Path(tempfile.mkdtemp(prefix="test_editing_"))
        logger.info(f"Created temporary test directory: {cls.test_dir}")
        
        # Path to the test video (using the same one as in test_full_workflow.py)
        cls.test_video = Path("test_video_2.mp4")
        if not cls.test_video.exists():
            raise FileNotFoundError(f"Test video not found: {cls.test_video}")
        
        # Get video info
        cls.video_info = get_video_info(cls.test_video)
        
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests have run."""
        # Remove the temporary directory and all its contents
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
            logger.info(f"Removed temporary test directory: {cls.test_dir}")
    
    def test_highlight_detector(self):
        """Test the HighlightDetector in isolation."""
        logger.info("Testing HighlightDetector...")
        
        from app.editing.processors.highlight_detector import HighlightDetector
        from app.editing.core.processor import ProcessingPipeline
        
        # Create a minimal pipeline with just the HighlightDetector
        pipeline = ProcessingPipeline()
        highlight_detector = HighlightDetector()
        pipeline.add_processor(highlight_detector)
        
        # Create output path
        output_path = self.test_dir / "highlights.json"
        
        try:
            logger.info(f"Running highlight detection on {self.test_video}")
            results = pipeline.run(
                input_path=self.test_video,
                output_path=output_path,
                video_info=self.video_info
            )
            
            # Check if the results contain highlight detector output
            self.assertIn('highlight_detector', results, "Highlight detector results not found in pipeline output")
            highlight_results = results['highlight_detector']
            
            # Check if segments were detected
            self.assertIn('segments', highlight_results, "No segments in highlight results")
            segments = highlight_results['segments']
            self.assertGreater(len(segments), 0, "No highlight segments were detected")
            
            logger.info(f"Detected {len(segments)} highlight segments")
            for i, segment in enumerate(segments, 1):
                logger.info(f"Segment {i}: {segment['start']:.2f}s - {segment['end']:.2f}s "
                           f"({segment['end']-segment['start']:.2f}s)")
            
            # Save the segments to a JSON file if we have any
            if segments:
                with open(output_path, 'w') as f:
                    json.dump(segments, f, indent=2)
                logger.info(f"Saved {len(segments)} highlight segments to {output_path}")
            else:
                logger.warning("No highlight segments to save")
            
        except Exception as e:
            logger.error(f"Error in test_highlight_detector: {str(e)}", exc_info=True)
            self.fail(f"Highlight detection failed: {str(e)}")

if __name__ == "__main__":
    unittest.main()
