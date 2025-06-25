"""
Core components for the video highlight pipeline.

This module defines the core interfaces and classes used throughout the pipeline.
"""
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable, Callable, Tuple
import logging
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Status of a processing operation."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class Progress:
    """Represents the progress of a processing operation."""
    current: int = 0
    total: int = 100
    status: ProcessingStatus = ProcessingStatus.PENDING
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def percent(self) -> float:
        """Get completion percentage (0-100)."""
        return (self.current / self.total * 100) if self.total > 0 else 0
    
    def update(self, current: Optional[int] = None, total: Optional[int] = None, 
              status: Optional[ProcessingStatus] = None, message: Optional[str] = None,
              **metadata):
        """Update progress with new values."""
        if current is not None:
            self.current = current
        if total is not None:
            self.total = total
        if status is not None:
            self.status = status
        if message is not None:
            self.message = message
        if metadata:
            self.metadata.update(metadata)
        return self


class CancellationToken:
    """Token for checking if an operation has been cancelled."""
    
    def __init__(self):
        self._cancelled = False
    
    def cancel(self):
        """Cancel the operation."""
        self._cancelled = True
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
    
    def check_cancelled(self):
        """Raise an exception if cancellation has been requested."""
        if self._cancelled:
            raise PipelineError("Operation was cancelled")


@runtime_checkable
class VideoProcessor(Protocol):
    """Protocol defining the interface for video processors.
    
    All processors in the pipeline must implement this interface.
    """
    
    def process(self, context: 'Context', progress_callback: Optional[Callable[['Progress'], None]] = None,
                cancel_token: Optional[CancellationToken] = None) -> 'Context':
        """Process the video context.
        
        Args:
            context: The current processing context
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token
            
        Returns:
            Updated context with processing results
            
        Raises:
            PipelineError: If processing fails or is cancelled
        """
        ...


@dataclass
class Segment:
    """A segment of video with associated metadata and features."""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    
    # Annotations from different analyzers
    scene_change: bool = False
    silent_ratio: float = 0.0
    word_count: int = 0
    audio_peaks: float = 0.0
    visual_motion: float = 0.0
    sentiment: float = 0.0
    
    # Optional features
    text: Optional[str] = None
    speaker: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Get the duration of the segment in seconds."""
        return self.end - self.start
    
    def to_feature_vector(self) -> np.ndarray:
        """Convert segment features to a numpy array for model inference."""
        return np.array([
            self.duration,
            float(self.scene_change),
            self.silent_ratio,
            self.word_count,
            self.audio_peaks,
            self.visual_motion,
            self.sentiment
        ])


@dataclass
class Context:
    """Shared context passed between pipeline stages."""
    video_path: str
    segments: List[Segment] = field(default_factory=list)
    
    # Store intermediate results from different stages
    silence_sections: List[Dict[str, float]] = field(default_factory=list)
    scene_changes: List[float] = field(default_factory=list)
    transcription: Optional[Dict] = None
    
    # Final outputs
    highlights: List[Segment] = field(default_factory=list)
    
    # Progress and status
    progress: Progress = field(default_factory=Progress)
    cancel_token: CancellationToken = field(default_factory=CancellationToken)
    
    # Metadata and configuration
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_progress(self, current: Optional[int] = None, total: Optional[int] = None, 
                       status: Optional[ProcessingStatus] = None, message: Optional[str] = None,
                       **metadata):
        """Update the progress of the current operation.
        
        Args:
            current: Current progress value
            total: Total value for completion
            status: Current status
            message: Status message
            **metadata: Additional metadata
        """
        self.progress.update(current, total, status, message, **metadata)
        return self.progress
    
    def check_cancelled(self):
        """Raise an exception if cancellation has been requested."""
        self.cancel_token.check_cancelled()
    
    def cancel(self):
        """Request cancellation of the current operation."""
        self.cancel_token.cancel()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to a dictionary for serialization."""
        return {
            'video_path': self.video_path,
            'segments': [
                {
                    'start': s.start,
                    'end': s.end,
                    'text': s.text,
                    'speaker': s.speaker,
                    'scene_change': s.scene_change,
                    'silence_ratio': s.silence_ratio,
                    'sentiment': s.sentiment
                }
                for s in self.segments
            ],
            'scene_changes': self.scene_changes,
            'silence_sections': self.silence_sections,
            'transcription': self.transcription,
            'highlights': self.highlights,
            'progress': {
                'current': self.progress.current,
                'total': self.progress.total,
                'status': self.progress.status.name,
                'message': self.progress.message,
                'metadata': self.progress.metadata
            },
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Context':
        """Create a Context from a dictionary."""
        context = cls(
            video_path=data['video_path'],
            segments=data.get('segments', []),
            scene_changes=data.get('scene_changes', []),
            silence_sections=data.get('silence_sections', []),
            transcription=data.get('transcription'),
            highlights=data.get('highlights', []),
            metadata=data.get('metadata', {})
        )
        
        # Restore progress
        if 'progress' in data:
            progress_data = data['progress']
            context.progress = Progress(
                current=progress_data.get('current', 0),
                total=progress_data.get('total', 100),
                status=ProcessingStatus[progress_data.get('status', 'PENDING')],
                message=progress_data.get('message', ''),
                metadata=progress_data.get('metadata', {})
            )
        
        # Reconstruct segments
        for seg_data in data.get('segments', []):
            segment = Segment(
                start=seg_data['start'],
                end=seg_data['end'],
                text=seg_data.get('text', ''),
                speaker=seg_data.get('speaker'),
                scene_change=seg_data.get('scene_change', False),
                silence_ratio=seg_data.get('silence_ratio', 0.0),
                sentiment=seg_data.get('sentiment', 0.0)
            )
            context.segments.append(segment)
        
        return context


class PipelineError(Exception):
    """Base class for pipeline-related errors."""
    pass


class PipelineCancelledError(PipelineError):
    """Raised when a pipeline operation is cancelled."""
    pass


class HighlightPipeline:
    """Orchestrates a series of video processors to generate highlights."""
    
    def __init__(self, stages: List[VideoProcessor]):
        """Initialize with an ordered list of processing stages."""
        self.stages = stages
    
    def cancel(self):
        """Request cancellation of the current pipeline execution."""
        self._cancel_token.cancel()
    
    def run(self, initial_context: Context, 
            progress_callback: Optional[Callable[[Progress], None]] = None,
            cancel_token: Optional[CancellationToken] = None) -> Context:
        """Run the pipeline on the given initial context.
        
        Args:
            initial_context: The initial context to process
            progress_callback: Optional callback for progress updates
            cancel_token: Optional cancellation token (not used in simplified version)
            
        Returns:
            The processed context after all stages
            
        Raises:
            PipelineError: If any processor fails
        """
        current_context = initial_context
        
        # Initialize progress
        total_steps = len(self.stages)
        
        try:
            for i, stage in enumerate(self.stages, 1):
                # Update progress
                if progress_callback:
                    progress = Progress(
                        current=i-1,
                        total=total_steps,
                        status=ProcessingStatus.RUNNING,
                        message=f"Running {stage.__class__.__name__}",
                        metadata={'processor': stage.__class__.__name__}
                    )
                    progress_callback(progress)
                
                logger.info(f"Running processor: {stage.__class__.__name__}")
                
                # Run the processor with progress and cancellation
                current_context = stage.process(
                    current_context,
                    progress_callback=progress_callback
                )
            
            # Mark as completed
            if progress_callback:
                progress = Progress(
                    current=total_steps,
                    total=total_steps,
                    status=ProcessingStatus.COMPLETED,
                    message="Processing completed successfully"
                )
                progress_callback(progress)
            
            return current_context
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            if progress_callback:
                progress = Progress(
                    current=0,
                    total=total_steps,
                    status=ProcessingStatus.FAILED,
                    message=f"Processing failed: {str(e)}"
                )
                progress_callback(progress)
            
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(f"Pipeline processing failed: {str(e)}") from e
    """Custom exception for pipeline-related errors."""
    pass
