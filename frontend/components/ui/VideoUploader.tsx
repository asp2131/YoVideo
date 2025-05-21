import { useState, useRef, useCallback } from 'react';

interface VideoUploaderProps {
  onVideoSelected: (file: File) => void;
  maxSizeMB?: number;
  acceptedFormats?: string[];
  className?: string;
}

export default function VideoUploader({ 
  onVideoSelected, 
  maxSizeMB = 500, 
  acceptedFormats = ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
  className = ''
}: VideoUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) {
      setIsDragging(true);
    }
  }, [isDragging]);

  const validateFile = useCallback((file: File): boolean => {
    setError(null);
    
    // Check file type
    if (!acceptedFormats.includes(file.type)) {
      setError(`Invalid file type. Please upload ${acceptedFormats.join(', ')} files.`);
      return false;
    }
    
    // Check file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > maxSizeMB) {
      setError(`File size exceeds ${maxSizeMB}MB limit.`);
      return false;
    }
    
    return true;
  }, [acceptedFormats, maxSizeMB]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const { files } = e.dataTransfer;
    if (files && files.length > 0) {
      const file = files[0]; // Only process the first file
      if (validateFile(file)) {
        onVideoSelected(file);
      }
    }
  }, [onVideoSelected, validateFile]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const { files } = e.target;
    if (files && files.length > 0) {
      const file = files[0]; // Only process the first file
      if (validateFile(file)) {
        onVideoSelected(file);
      }
    }
  }, [onVideoSelected, validateFile]);

  const handleButtonClick = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, []);

  const formatAcceptedTypes = acceptedFormats.join(',');
  const displayFormats = acceptedFormats.map(format => format.split('/')[1].toUpperCase()).join(', ');

  return (
    <div className={`${className}`}>
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
        </svg>
        <div className="mt-4 flex text-sm text-gray-600 justify-center">
          <button
            type="button"
            className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            onClick={handleButtonClick}
          >
            <span>Upload a video</span>
            <input
              ref={fileInputRef}
              id="file-upload"
              name="file-upload"
              type="file"
              className="sr-only"
              accept={formatAcceptedTypes}
              onChange={handleFileInputChange}
            />
          </button>
          <p className="pl-1">or drag and drop</p>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          {displayFormats} up to {maxSizeMB}MB
        </p>
        {error && (
          <div className="mt-2 text-sm text-red-600">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
