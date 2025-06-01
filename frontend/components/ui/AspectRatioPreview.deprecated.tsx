import { useState } from 'react';

interface AspectRatio {
  id: string;
  name: string;
  value: string; // e.g., "16:9", "9:16", "1:1"
  width: number;
  height: number;
}

interface AspectRatioPreviewProps {
  videoUrl: string;
  onAspectRatioChange: (aspectRatio: AspectRatio) => void;
  selectedAspectRatioId?: string;
  className?: string;
}

export default function AspectRatioPreview({
  videoUrl,
  onAspectRatioChange,
  selectedAspectRatioId,
  className = ''
}: AspectRatioPreviewProps) {
  // Predefined aspect ratios
  const aspectRatios: AspectRatio[] = [
    { id: 'landscape', name: 'Landscape (16:9)', value: '16:9', width: 16, height: 9 },
    { id: 'portrait', name: 'Portrait (9:16)', value: '9:16', width: 9, height: 16 },
    { id: 'square', name: 'Square (1:1)', value: '1:1', width: 1, height: 1 },
    { id: 'instagram', name: 'Instagram (4:5)', value: '4:5', width: 4, height: 5 },
    { id: 'cinema', name: 'Cinema (21:9)', value: '21:9', width: 21, height: 9 },
    { id: 'tiktok', name: 'TikTok (9:16)', value: '9:16', width: 9, height: 16 },
  ];

  // Find the selected aspect ratio or default to the first one
  const selectedAspectRatio = aspectRatios.find(ar => ar.id === selectedAspectRatioId) || aspectRatios[0];
  
  // Calculate styles for the preview container based on the selected aspect ratio
  const getPreviewStyle = (aspectRatio: AspectRatio) => {
    const { width, height } = aspectRatio;
    return {
      aspectRatio: `${width} / ${height}`,
    };
  };

  return (
    <div className={`${className}`}>
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Aspect Ratio Preview</h3>
        
        {/* Aspect ratio selection */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {aspectRatios.map((aspectRatio) => (
            <button
              key={aspectRatio.id}
              className={`p-3 border rounded-lg text-center transition-colors ${
                selectedAspectRatio.id === aspectRatio.id
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-blue-300 text-gray-700'
              }`}
              onClick={() => onAspectRatioChange(aspectRatio)}
            >
              <div 
                className="mx-auto mb-2 bg-gray-200 border border-gray-300"
                style={{ 
                  width: '60px', 
                  height: `${60 * (aspectRatio.height / aspectRatio.width)}px`,
                  maxHeight: '80px'
                }}
              ></div>
              <span className="text-sm font-medium">{aspectRatio.name}</span>
            </button>
          ))}
        </div>
        
        {/* Video preview with selected aspect ratio */}
        <div className="bg-black p-4 rounded-lg">
          <div className="max-w-md mx-auto">
            <div 
              className="relative bg-gray-800 overflow-hidden mx-auto"
              style={getPreviewStyle(selectedAspectRatio)}
            >
              {videoUrl ? (
                <video
                  src={videoUrl}
                  className="absolute inset-0 w-full h-full object-cover"
                  controls
                  playsInline
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-gray-400">
                    <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                    </svg>
                    <p className="text-sm">Upload a video to preview</p>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-4 text-center">
              <p className="text-sm text-gray-300">
                Preview: {selectedAspectRatio.name} ({selectedAspectRatio.value})
              </p>
            </div>
          </div>
        </div>
        
        {/* Additional export options */}
        <div className="mt-6 bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3">Export Settings</h4>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Resolution
              </label>
              <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
                <option>1080p (Full HD)</option>
                <option>720p (HD)</option>
                <option>480p (SD)</option>
                <option>360p (Low)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Format
              </label>
              <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
                <option>MP4 (H.264)</option>
                <option>WebM (VP9)</option>
                <option>MOV (ProRes)</option>
                <option>GIF (Animated)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quality
              </label>
              <div className="flex items-center">
                <span className="text-xs text-gray-500 mr-2">Low</span>
                <input
                  type="range"
                  min="1"
                  max="5"
                  defaultValue="4"
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <span className="text-xs text-gray-500 ml-2">High</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
