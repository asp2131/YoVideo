import { useState, useRef, useEffect } from 'react';

interface Transcription {
  id: string;
  text: string;
  startTime: number; // in seconds
  endTime: number; // in seconds
}

interface VideoPlayerProps {
  videoUrl: string;
  transcription?: Transcription[];
  onTimeUpdate?: (currentTime: number) => void;
  className?: string;
}

export default function VideoPlayer({ 
  videoUrl, 
  transcription = [], 
  onTimeUpdate,
  className = ''
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [activeTranscriptId, setActiveTranscriptId] = useState<string | null>(null);

  // Handle video metadata loaded
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [videoUrl]);

  // Handle time updates
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      if (onTimeUpdate) {
        onTimeUpdate(video.currentTime);
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [onTimeUpdate]);

  // Handle play/pause state
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    return () => {
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
    };
  }, []);

  // Update active transcript based on current time
  useEffect(() => {
    if (transcription.length === 0) return;

    const activeSegment = transcription.find(
      segment => currentTime >= segment.startTime && currentTime <= segment.endTime
    );

    setActiveTranscriptId(activeSegment?.id || null);
  }, [currentTime, transcription]);

  // Play/pause toggle
  const togglePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
  };

  // Seek to a specific time
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;

    const newTime = parseFloat(e.target.value);
    video.currentTime = newTime;
    setCurrentTime(newTime);
  };

  // Update volume
  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;

    const newVolume = parseFloat(e.target.value);
    video.volume = newVolume;
    setVolume(newVolume);
  };

  // Format time (seconds to MM:SS)
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Jump to transcript segment
  const jumpToSegment = (startTime: number) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = startTime;
    if (!isPlaying) {
      video.play();
    }
  };

  return (
    <div className={`${className}`}>
      <div className="relative">
        {/* Video element */}
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full rounded-lg"
          playsInline
        />

        {/* Custom controls */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4">
          <div className="flex flex-col gap-2">
            {/* Progress bar */}
            <input
              type="range"
              min="0"
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            
            <div className="flex justify-between items-center">
              {/* Play/pause button */}
              <button
                onClick={togglePlayPause}
                className="text-white hover:text-blue-300 focus:outline-none"
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isPlaying ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"></path>
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M8 5v14l11-7-11-7z"></path>
                  </svg>
                )}
              </button>

              {/* Time display */}
              <div className="text-white text-sm">
                {formatTime(currentTime)} / {formatTime(duration)}
              </div>

              {/* Volume control */}
              <div className="flex items-center">
                <button
                  onClick={() => {
                    const video = videoRef.current;
                    if (!video) return;
                    const newVolume = volume === 0 ? 1 : 0;
                    video.volume = newVolume;
                    setVolume(newVolume);
                  }}
                  className="text-white hover:text-blue-300 focus:outline-none mr-2"
                  aria-label={volume === 0 ? 'Unmute' : 'Mute'}
                >
                  {volume === 0 ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3.63 3.63a.996.996 0 000 1.41L7.29 8.7 7 9H4c-.55 0-1 .45-1 1v4c0 .55.45 1 1 1h3l3.29 3.29c.63.63 1.71.18 1.71-.71v-4.17l4.18 4.18c-.49.37-1.02.68-1.6.91-.36.15-.58.53-.58.92 0 .72.73 1.18 1.39.91.8-.33 1.55-.77 2.22-1.31l1.34 1.34a.996.996 0 101.41-1.41L5.05 3.63c-.39-.39-1.02-.39-1.42 0zM19 12c0 .82-.15 1.61-.41 2.34l1.53 1.53c.56-1.17.88-2.48.88-3.87 0-3.83-2.4-7.11-5.78-8.4-.59-.23-1.22.23-1.22.86v.19c0 .38.25.71.61.85C17.18 6.54 19 9.06 19 12zm-8.71-6.29l-.17.17L12 7.76V6.41c0-.89-1.08-1.33-1.71-.7zM16.5 12A4.5 4.5 0 0014 7.97v1.79l2.48 2.48c.01-.08.02-.16.02-.24z"></path>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"></path>
                    </svg>
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="w-16 h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Transcription display */}
      {transcription.length > 0 && (
        <div className="mt-4 bg-gray-50 rounded-lg p-4 max-h-60 overflow-y-auto">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Transcription</h3>
          <div className="space-y-2">
            {transcription.map((segment) => (
              <div
                key={segment.id}
                className={`p-2 rounded cursor-pointer ${
                  activeTranscriptId === segment.id ? 'bg-blue-100' : 'hover:bg-gray-100'
                }`}
                onClick={() => jumpToSegment(segment.startTime)}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs text-gray-500">
                    {formatTime(segment.startTime)} - {formatTime(segment.endTime)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      jumpToSegment(segment.startTime);
                    }}
                    className="text-blue-600 hover:text-blue-800 text-xs"
                  >
                    Jump
                  </button>
                </div>
                <p className="text-sm text-gray-800">{segment.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
