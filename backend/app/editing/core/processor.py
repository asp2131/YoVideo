import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

class VideoProcessor(ABC):
    """Base class for all video processing operations."""
    
    @abstractmethod
    def process(self, input_path: Path, output_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Process the video file.
        
        Args:
            input_path: Path to the input video file
            output_path: Path where the processed video should be saved
            **kwargs: Additional processor-specific parameters
            
        Returns:
            Dict containing processing results and metadata
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the processor."""
        pass


class ProcessingPipeline:
    """Manages a sequence of video processors."""
    
    def __init__(self):
        self.processors = []
    
    def add_processor(self, processor: VideoProcessor):
        """Add a processor to the pipeline."""
        self.processors.append(processor)
        return self
    
    def run(self, input_path: Path, output_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Run all processors in sequence.
        
        Args:
            input_path: Path to the input video file
            output_path: Path where the final processed video should be saved
            **kwargs: Additional parameters to pass to processors
            
        Returns:
            Dict containing combined results from all processors
        """
        current_input = input_path
        temp_files = []
        results = {}
        
        try:
            for i, processor in enumerate(self.processors):
                # For all but the last processor, use a temporary file
                if i < len(self.processors) - 1:
                    import tempfile
                    fd, temp_path = tempfile.mkstemp(suffix='.mp4')
                    os.close(fd)
                    temp_files.append(Path(temp_path))
                    current_output = temp_files[-1]
                else:
                    current_output = output_path
                
                # Run the processor
                processor_result = processor.process(
                    input_path=current_input,
                    output_path=current_output,
                    **kwargs
                )
                
                # Store results
                results[processor.name] = processor_result
                current_input = current_output
                
            return results
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()


class VideoEditingError(Exception):
    """Base exception for video editing errors."""
    pass
