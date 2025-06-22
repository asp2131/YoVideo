# Video Editing Module

This module provides automatic video editing capabilities for the VideoThingy application. It's designed to be extensible and modular, allowing for easy addition of new editing features.

## Features

- **Modular Architecture**: Easily add new processors to the pipeline
- **Built-in Processors**:
  - `SilenceRemover`: Automatically detects and removes silent portions from videos
  - `SceneDetector`: Identifies scene changes in videos
- **Extensible**: Create custom processors by extending the `VideoProcessor` base class
- **Task Integration**: Seamlessly integrates with Celery for background processing

## Usage

### Basic Usage

```python
from app.editing import get_default_pipeline

# Create a processing pipeline
pipeline = get_default_pipeline()

# Process a video
results = pipeline.run(
    input_path="input.mp4",
    output_path="output.mp4"
)
```

### Creating Custom Processors

1. Create a new processor class:

```python
from pathlib import Path
from typing import Dict, Any
from app.editing.core.processor import VideoProcessor

class MyCustomProcessor(VideoProcessor):
    @property
    def name(self) -> str:
        return "my_custom_processor"
    
    def process(self, input_path: Path, output_path: Path, **kwargs) -> Dict[str, Any]:
        # Your processing logic here
        return {"status": "completed"}
```

2. Register your processor in the factory:

```python
# In your module's __init__.py
from app.editing.factory import PROCESSOR_REGISTRY
from .my_processor import MyCustomProcessor

PROCESSOR_REGISTRY["my_processor"] = MyCustomProcessor
```

## Available Processors

### SilenceRemover

Removes silent portions from videos.

**Parameters:**
- `silence_threshold` (float): Volume threshold in dB (default: -30.0)
- `silence_duration` (float): Minimum duration of silence to remove in seconds (default: 0.5)

### SceneDetector

Detects scene changes in videos.

**Parameters:**
- `threshold` (float): Threshold for scene change detection (default: 30.0)
- `min_scene_len` (float): Minimum length of a scene in seconds (default: 1.5)

## Task Integration

The module includes a Celery task for background processing:

```python
from app.tasks.video_editing import process_video_editing

# Start processing in the background
result = process_video_editing.delay(
    project_id="project_123",
    input_video_path="videos/input.mp4",
    output_video_path="videos/processed.mp4"
)
```

## Development

### Adding New Processors

1. Create a new Python file in `app/editing/processors/`
2. Define your processor class extending `VideoProcessor`
3. Import the processor in `app/editing/__init__.py`
4. Register it in the `PROCESSOR_REGISTRY` if needed

### Testing

Run the test suite:

```bash
pytest tests/editing/
```

## Dependencies

- FFmpeg (system dependency)
- OpenCV
- scenedetect
- scikit-video
- librosa
- soundfile

## License

MIT
