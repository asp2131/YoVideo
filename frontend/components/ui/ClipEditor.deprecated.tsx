import { useState, useRef, useEffect } from 'react';

interface ClipRange {
  startTime: number;
  endTime: number;
}

interface ClipEditorProps {
  videoUrl: string;
  duration: number;
  onClipChange: (clip: ClipRange) => void;
  initialClip?: ClipRange;
  className?: string;
}

export default function ClipEditor({
  videoUrl,
  duration,
  onClipChange,
  initialClip,
  className = ''
}: ClipEditorProps) {
  const [clipRange, setClipRange] = useState<ClipRange>(
    initialClip || { startTime: 0, endTime: duration }
  );
  const [isDraggingStart, setIsDraggingStart] = useState(false);
  const [isDraggingEnd, setIsDraggingEnd] = useState(false);
  const [isDraggingMiddle, setIsDraggingMiddle] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartValue, setDragStartValue] = useState(0);
  const [dragEndValue, setDragEndValue] = useState(0);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Update clip range when duration changes
  useEffect(() => {
    if (duration > 0 && (!initialClip || initialClip.endTime > duration)) {
      setClipRange(prev => ({
        startTime: prev.startTime,
        endTime: Math.min(prev.endTime, duration)
      }));
    }
  }, [duration, initialClip]);

  // Notify parent component when clip range changes
  useEffect(() => {
    onClipChange(clipRange);
  }, [clipRange, onClipChange]);

  // Handle mouse move for dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!timelineRef.current || (!isDraggingStart && !isDraggingEnd && !isDraggingMiddle)) {
        return;
      }

      const timelineRect = timelineRef.current.getBoundingClientRect();
      const timelineWidth = timelineRect.width;
      const offsetX = e.clientX - timelineRect.left;
      const ratio = Math.max(0, Math.min(1, offsetX / timelineWidth));
      const newTime = ratio * duration;

      if (isDraggingStart) {
        const newStartTime = Math.min(newTime, clipRange.endTime - 0.5);
        setClipRange(prev => ({
          ...prev,
          startTime: Math.max(0, newStartTime)
        }));
      } else if (isDraggingEnd) {
        const newEndTime = Math.max(newTime, clipRange.startTime + 0.5);
        setClipRange(prev => ({
          ...prev,
          endTime: Math.min(duration, newEndTime)
        }));
      } else if (isDraggingMiddle) {
        const deltaX = e.clientX - dragStartX;
        const deltaTime = (deltaX / timelineWidth) * duration;
        
        const clipDuration = dragEndValue - dragStartValue;
        let newStartTime = dragStartValue + deltaTime;
        let newEndTime = dragEndValue + deltaTime;
        
        // Ensure clip stays within bounds
        if (newStartTime < 0) {
          newStartTime = 0;
          newEndTime = clipDuration;
        }
        
        if (newEndTime > duration) {
          newEndTime = duration;
          newStartTime = duration - clipDuration;
        }
        
        setClipRange({
          startTime: newStartTime,
          endTime: newEndTime
        });
      }
    };

    const handleMouseUp = () => {
      setIsDraggingStart(false);
      setIsDraggingEnd(false);
      setIsDraggingMiddle(false);
    };

    if (isDraggingStart || isDraggingEnd || isDraggingMiddle) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingStart, isDraggingEnd, isDraggingMiddle, clipRange, duration, dragStartX, dragStartValue, dragEndValue]);

  // Format time (seconds to MM:SS)
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Calculate positions for timeline elements
  const startPosition = `${(clipRange.startTime / duration) * 100}%`;
  const endPosition = `${(clipRange.endTime / duration) * 100}%`;
  const clipWidth = `${((clipRange.endTime - clipRange.startTime) / duration) * 100}%`;

  return (
    <div className={`${className}`}>
      <div className="mb-4">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Clip Selection</h3>
        <div className="flex justify-between text-sm text-gray-500 mb-1">
          <span>Start: {formatTime(clipRange.startTime)}</span>
          <span>End: {formatTime(clipRange.endTime)}</span>
          <span>Duration: {formatTime(clipRange.endTime - clipRange.startTime)}</span>
        </div>
      </div>

      {/* Timeline */}
      <div 
        ref={timelineRef}
        className="relative h-12 bg-gray-200 rounded-lg mb-4 cursor-pointer"
      >
        {/* Selected clip area */}
        <div
          className="absolute top-0 bottom-0 bg-blue-200 border-l-2 border-r-2 border-blue-500"
          style={{
            left: startPosition,
            width: clipWidth
          }}
          onMouseDown={(e) => {
            e.preventDefault();
            setIsDraggingMiddle(true);
            setDragStartX(e.clientX);
            setDragStartValue(clipRange.startTime);
            setDragEndValue(clipRange.endTime);
          }}
        />

        {/* Start handle */}
        <div
          className="absolute top-0 bottom-0 w-4 bg-blue-500 cursor-ew-resize flex items-center justify-center"
          style={{ left: startPosition, marginLeft: '-8px' }}
          onMouseDown={(e) => {
            e.preventDefault();
            setIsDraggingStart(true);
          }}
        >
          <div className="w-1 h-6 bg-white rounded-full"></div>
        </div>

        {/* End handle */}
        <div
          className="absolute top-0 bottom-0 w-4 bg-blue-500 cursor-ew-resize flex items-center justify-center"
          style={{ left: endPosition, marginLeft: '-8px' }}
          onMouseDown={(e) => {
            e.preventDefault();
            setIsDraggingEnd(true);
          }}
        >
          <div className="w-1 h-6 bg-white rounded-full"></div>
        </div>

        {/* Time markers */}
        <div className="absolute bottom-0 left-0 right-0 flex justify-between px-2 text-xs text-gray-500">
          <span>0:00</span>
          <span>{formatTime(duration / 4)}</span>
          <span>{formatTime(duration / 2)}</span>
          <span>{formatTime(duration * 3 / 4)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex space-x-2">
        <button
          onClick={() => setClipRange({ startTime: 0, endTime: duration })}
          className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
        >
          Reset
        </button>
        <button
          onClick={() => {
            // Trim 5% from start and end as a quick trim
            const trimAmount = duration * 0.05;
            setClipRange({
              startTime: Math.min(trimAmount, clipRange.endTime - 1),
              endTime: Math.max(duration - trimAmount, clipRange.startTime + 1)
            });
          }}
          className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
        >
          Auto Trim
        </button>
        <button
          onClick={() => {
            // Create a 15-second clip centered on the current position
            const center = (clipRange.startTime + clipRange.endTime) / 2;
            const halfDuration = 7.5; // 15 seconds / 2
            setClipRange({
              startTime: Math.max(0, center - halfDuration),
              endTime: Math.min(duration, center + halfDuration)
            });
          }}
          className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
        >
          15s Clip
        </button>
        <button
          onClick={() => {
            // Create a 30-second clip centered on the current position
            const center = (clipRange.startTime + clipRange.endTime) / 2;
            const halfDuration = 15; // 30 seconds / 2
            setClipRange({
              startTime: Math.max(0, center - halfDuration),
              endTime: Math.min(duration, center + halfDuration)
            });
          }}
          className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
        >
          30s Clip
        </button>
      </div>

      {/* Preview of selected clip */}
      <div className="mt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Clip Preview</h3>
        <div className="bg-black rounded-lg overflow-hidden">
          {videoUrl && (
            <video
              src={`${videoUrl}#t=${clipRange.startTime},${clipRange.endTime}`}
              className="w-full"
              controls
              playsInline
            />
          )}
        </div>
      </div>
    </div>
  );
}
