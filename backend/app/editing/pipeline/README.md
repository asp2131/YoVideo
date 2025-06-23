# Video Highlight Pipeline

A modular and extensible pipeline for processing videos to extract highlights and key segments.

## Overview

The video highlight pipeline processes video content through a series of stages to identify and extract the most interesting segments. The pipeline is designed to be:

- **Modular**: Each processing step is a self-contained component
- **Configurable**: Customize behavior through parameters and configuration
- **Extensible**: Easily add new processing steps or modify existing ones
- **Type-safe**: Uses Python dataclasses for better IDE support and type checking

## Core Components

### 1. Pipeline Structure

- `HighlightPipeline`: Orchestrates the execution of processors in sequence
- `VideoProcessor`: Protocol/interface that all processors must implement
- `Context`: Shared state passed between processors
- `Segment`: Represents a segment of video with metadata

### 2. Built-in Processors

1. **SilenceRemover**: Identifies and removes silent sections
2. **SceneDetector**: Detects scene changes in the video
3. **IntelligentSegmenter**: Creates content-aware segments based on transcription and analysis
4. **EnhancedHighlightDetector**: Scores and selects the best segments as highlights

## Quick Start

```python
from app.editing.pipeline.default_pipeline import process_video

# Process a video with default settings
results = process_video(
    video_path="path/to/input.mp4",
    output_dir="path/to/output"
)

# Access the highlights
for highlight in results['highlights']:
    print(f"Highlight: {highlight['start']:.1f}s - {highlight['end']:.1f}s")
    print(f"  Text: {highlight.get('text', '')}")
    print(f"  Score: {highlight.get('score', 0):.2f}")
```

## Configuration

Customize the pipeline behavior by passing a configuration dictionary:

```python
config = {
    'min_highlight_duration': 3.0,  # Minimum highlight duration in seconds
    'max_highlight_duration': 20.0,  # Maximum highlight duration
    'target_total_duration': 120.0,  # Target total duration of all highlights
    'silence_threshold': -35.0,      # dB threshold for silence detection
    'scene_threshold': 25.0,         # Threshold for scene change detection
    'use_scene_boundaries': True,    # Respect scene boundaries in segmentation
    'respect_silence': True          # Avoid cutting in the middle of speech
}

results = process_video("input.mp4", config=config)
```

## Advanced Usage

### Creating a Custom Pipeline

```python
from app.editing.pipeline import HighlightPipeline, Context
from app.editing.processors import SilenceRemover, SceneDetector
from app.editing.segmenters import IntelligentSegmenter
from app.editing.processors import EnhancedHighlightDetector

# Create custom processors
silence_remover = SilenceRemover(silence_threshold=-30.0)
scene_detector = SceneDetector(threshold=30.0)
segmenter = IntelligentSegmenter(min_segment_duration=2.0, max_segment_duration=15.0)
highlight_detector = EnhancedHighlightDetector(
    min_duration=2.0,
    max_duration=15.0,
    target_total_duration=60.0
)

# Assemble the pipeline
pipeline = HighlightPipeline([
    silence_remover,
    scene_detector,
    segmenter,
    highlight_detector
])

# Run the pipeline
context = Context(
    video_path="input.mp4",
    output_dir="output"
)

result_context = pipeline.run(context)
```

### Creating Custom Processors

Create a new processor by implementing the `VideoProcessor` protocol:

```python
from typing import Optional
from dataclasses import dataclass
from app.editing.pipeline import VideoProcessor, Context

@dataclass
class MyCustomProcessor(VideoProcessor):
    """A custom processor that does something interesting."""
    
    some_parameter: float = 1.0
    
    def process(self, context: Context) -> Context:
        """Process the video context."""
        # Your processing logic here
        context.metadata['custom_processor'] = {
            'processed': True,
            'some_value': self.some_parameter
        }
        return context
```

## Command Line Interface

A simple CLI is provided for testing and batch processing:

```bash
# Basic usage
python -m tests.test_pipeline path/to/input.mp4

# With custom output directory
python -m tests.test_pipeline input.mp4 --output-dir output/

# Save results to JSON
python -m tests.test_pipeline input.mp4 --save-json

# Use a custom config file
python -m tests.test_pipeline input.mp4 --config config.json
```

## Testing

Run the unit tests:

```bash
pytest tests/unit/test_pipeline_integration.py -v
```

## Performance Considerations

- For large videos, consider processing in chunks
- Enable parallel processing where possible
- Cache intermediate results when appropriate
- Monitor memory usage for long-running processes

## Extending the Pipeline

1. **Add New Processors**: Create new classes that implement the `VideoProcessor` protocol
2. **Modify Existing Processors**: Subclass and override methods as needed
3. **Add New Features**: Extend the `Context` or `Segment` classes with additional attributes

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
