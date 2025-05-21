import { useState } from 'react';

interface ExportFormat {
  id: string;
  name: string;
  extension: string;
  quality: string[];
  icon: string;
}

interface DownloadOption {
  format: string;
  quality: string;
  withCaptions: boolean;
}

interface DownloadInterfaceProps {
  videoUrl?: string;
  thumbnailUrl?: string;
  videoTitle?: string;
  isProcessing?: boolean;
  processingProgress?: number;
  onExport: (options: DownloadOption) => void;
  className?: string;
}

export default function DownloadInterface({
  videoUrl,
  thumbnailUrl,
  videoTitle = 'Untitled Video',
  isProcessing = false,
  processingProgress = 0,
  onExport,
  className = ''
}: DownloadInterfaceProps) {
  const [selectedFormat, setSelectedFormat] = useState<string>('mp4');
  const [selectedQuality, setSelectedQuality] = useState<string>('high');
  const [withCaptions, setWithCaptions] = useState<boolean>(true);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState<boolean>(false);

  // Available export formats
  const exportFormats: ExportFormat[] = [
    {
      id: 'mp4',
      name: 'MP4',
      extension: '.mp4',
      quality: ['low', 'medium', 'high', 'ultra'],
      icon: 'M19 9l-7 4-7-4V6l7 4 7-4v3zm-7 10a1 1 0 01-1-1V9.5l-6-3.25V15l7 4 7-4V6.25l-6 3.25V18c0 .552-.448 1-1 1z'
    },
    {
      id: 'webm',
      name: 'WebM',
      extension: '.webm',
      quality: ['low', 'medium', 'high'],
      icon: 'M19 9l-7 4-7-4V6l7 4 7-4v3zm-7 10a1 1 0 01-1-1V9.5l-6-3.25V15l7 4 7-4V6.25l-6 3.25V18c0 .552-.448 1-1 1z'
    },
    {
      id: 'mov',
      name: 'QuickTime',
      extension: '.mov',
      quality: ['medium', 'high', 'ultra'],
      icon: 'M19 9l-7 4-7-4V6l7 4 7-4v3zm-7 10a1 1 0 01-1-1V9.5l-6-3.25V15l7 4 7-4V6.25l-6 3.25V18c0 .552-.448 1-1 1z'
    },
    {
      id: 'gif',
      name: 'GIF',
      extension: '.gif',
      quality: ['low', 'medium', 'high'],
      icon: 'M19 9l-7 4-7-4V6l7 4 7-4v3zm-7 10a1 1 0 01-1-1V9.5l-6-3.25V15l7 4 7-4V6.25l-6 3.25V18c0 .552-.448 1-1 1z'
    }
  ];

  // Get the current selected format
  const currentFormat = exportFormats.find(format => format.id === selectedFormat) || exportFormats[0];

  // Handle export button click
  const handleExport = () => {
    onExport({
      format: selectedFormat,
      quality: selectedQuality,
      withCaptions
    });
  };

  // Format file size (mock function - in a real app this would calculate based on format/quality)
  const getEstimatedFileSize = (format: string, quality: string): string => {
    const baseSizes: Record<string, number> = {
      mp4: 10,
      webm: 8,
      mov: 15,
      gif: 20
    };
    
    const qualityMultipliers: Record<string, number> = {
      low: 0.5,
      medium: 1,
      high: 2,
      ultra: 3.5
    };
    
    const estimatedSize = baseSizes[format] * qualityMultipliers[quality];
    
    if (estimatedSize < 1) {
      return `${(estimatedSize * 1000).toFixed(0)} KB`;
    }
    
    return `${estimatedSize.toFixed(1)} MB`;
  };

  // Quality label mapping
  const qualityLabels: Record<string, string> = {
    low: '480p (SD)',
    medium: '720p (HD)',
    high: '1080p (Full HD)',
    ultra: '4K (Ultra HD)'
  };

  return (
    <div className={`${className}`}>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Export Video</h3>
        </div>
        
        {/* Video preview */}
        <div className="p-4 bg-gray-50">
          <div className="flex items-center">
            <div className="flex-shrink-0 w-16 h-16 bg-gray-200 rounded overflow-hidden relative">
              {thumbnailUrl ? (
                <img 
                  src={thumbnailUrl} 
                  alt={videoTitle} 
                  className="w-full h-full object-cover" 
                />
              ) : (
                <div className="flex items-center justify-center h-full bg-gray-300">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                  </svg>
                </div>
              )}
            </div>
            <div className="ml-4">
              <h4 className="text-sm font-medium text-gray-900">{videoTitle}</h4>
              {videoUrl && (
                <p className="text-xs text-gray-500 mt-1">Ready to export</p>
              )}
            </div>
          </div>
        </div>
        
        {/* Export options */}
        <div className="p-4">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Format
            </label>
            <div className="grid grid-cols-4 gap-2">
              {exportFormats.map((format) => (
                <button
                  key={format.id}
                  className={`p-3 border rounded-lg text-center transition-colors ${
                    selectedFormat === format.id
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-blue-300 text-gray-700'
                  }`}
                  onClick={() => {
                    setSelectedFormat(format.id);
                    // If the selected quality isn't available in this format, choose the highest available
                    if (!format.quality.includes(selectedQuality)) {
                      setSelectedQuality(format.quality[format.quality.length - 1]);
                    }
                  }}
                >
                  <svg className="w-6 h-6 mx-auto mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={format.icon}></path>
                  </svg>
                  <span className="text-sm">{format.name}</span>
                </button>
              ))}
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Quality
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {currentFormat.quality.map((quality) => (
                <button
                  key={quality}
                  className={`p-2 border rounded-lg text-center transition-colors ${
                    selectedQuality === quality
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-blue-300 text-gray-700'
                  }`}
                  onClick={() => setSelectedQuality(quality)}
                >
                  <span className="text-sm">{qualityLabels[quality]}</span>
                </button>
              ))}
            </div>
          </div>
          
          <div className="mb-4">
            <div className="flex items-center">
              <input
                id="with-captions"
                type="checkbox"
                checked={withCaptions}
                onChange={(e) => setWithCaptions(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="with-captions" className="ml-2 block text-sm text-gray-700">
                Include captions in video
              </label>
            </div>
          </div>
          
          <div className="mb-4">
            <button
              type="button"
              onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
              className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
            >
              <svg className={`w-4 h-4 mr-1 transition-transform ${showAdvancedOptions ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
              </svg>
              Advanced options
            </button>
            
            {showAdvancedOptions && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Frame Rate
                    </label>
                    <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
                      <option>30 fps</option>
                      <option>60 fps</option>
                      <option>24 fps (Film)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Audio Bitrate
                    </label>
                    <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
                      <option>128 kbps</option>
                      <option>192 kbps</option>
                      <option>256 kbps</option>
                      <option>320 kbps</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              Estimated size: {getEstimatedFileSize(selectedFormat, selectedQuality)}
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={isProcessing || !videoUrl}
              className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white ${
                isProcessing || !videoUrl
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
              }`}
            >
              {isProcessing ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Processing ({processingProgress}%)
                </>
              ) : (
                <>
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                  </svg>
                  Export Video
                </>
              )}
            </button>
          </div>
        </div>
        
        {/* Processing status */}
        {isProcessing && (
          <div className="p-4 bg-blue-50 border-t border-blue-100">
            <div className="flex items-center">
              <div className="w-full">
                <div className="flex justify-between text-xs text-blue-700 mb-1">
                  <span>Processing video...</span>
                  <span>{processingProgress}%</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${processingProgress}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
