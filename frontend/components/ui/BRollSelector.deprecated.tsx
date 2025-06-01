import { useState } from 'react';
import Image from 'next/image';
import VideoUploader from './VideoUploader';

interface BRoll {
  id: string;
  title: string;
  duration: string;
  thumbnailUrl: string;
  videoUrl: string;
  tags: string[];
}

interface BRollInsertionPoint {
  id: string;
  timestamp: number;
  duration: number;
  bRollId?: string;
}

interface BRollSelectorProps {
  insertionPoints: BRollInsertionPoint[];
  onInsertionPointsChange: (points: BRollInsertionPoint[]) => void;
  onBRollUpload: (file: File) => void;
  className?: string;
}

export default function BRollSelector({
  insertionPoints,
  onInsertionPointsChange,
  onBRollUpload,
  className = ''
}: BRollSelectorProps) {
  const [activeTab, setActiveTab] = useState<'library' | 'suggestions'>('library');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedBRoll, setSelectedBRoll] = useState<string | null>(null);

  // Sample B-roll data - in a real app, this would come from an API
  const bRollLibrary: BRoll[] = [
    {
      id: 'br-1',
      title: 'City Traffic',
      duration: '0:15',
      thumbnailUrl: '',
      videoUrl: '',
      tags: ['city', 'urban', 'traffic']
    },
    {
      id: 'br-2',
      title: 'Nature Scenery',
      duration: '0:20',
      thumbnailUrl: '',
      videoUrl: '',
      tags: ['nature', 'landscape', 'peaceful']
    },
    {
      id: 'br-3',
      title: 'Office Environment',
      duration: '0:12',
      thumbnailUrl: '',
      videoUrl: '',
      tags: ['business', 'office', 'work']
    },
    {
      id: 'br-4',
      title: 'Technology Close-up',
      duration: '0:18',
      thumbnailUrl: '',
      videoUrl: '',
      tags: ['technology', 'gadgets', 'close-up']
    },
    {
      id: 'br-5',
      title: 'People Walking',
      duration: '0:22',
      thumbnailUrl: '',
      videoUrl: '',
      tags: ['people', 'walking', 'crowd']
    }
  ];

  // Get all unique tags
  const allTags = Array.from(new Set(bRollLibrary.flatMap(br => br.tags)));

  // Filter B-roll based on search query and selected tags
  const filteredBRoll = bRollLibrary.filter(bRoll => {
    const matchesSearch = bRoll.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTags = selectedTags.length === 0 || selectedTags.some(tag => bRoll.tags.includes(tag));
    return matchesSearch && matchesTags;
  });

  // Format time (seconds to MM:SS)
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Add a new insertion point
  const addInsertionPoint = () => {
    // Find the last insertion point's timestamp or start at 0
    const lastPoint = insertionPoints.length > 0 
      ? insertionPoints[insertionPoints.length - 1] 
      : { timestamp: 0, duration: 0 };
    
    const newPoint: BRollInsertionPoint = {
      id: `ip-${Date.now()}`,
      timestamp: lastPoint.timestamp + lastPoint.duration + 5, // 5 seconds after the last one ends
      duration: 3, // Default 3-second duration
    };
    
    onInsertionPointsChange([...insertionPoints, newPoint]);
  };

  // Update an insertion point
  const updateInsertionPoint = (id: string, field: keyof BRollInsertionPoint, value: number | string | undefined) => {
    onInsertionPointsChange(
      insertionPoints.map(point => 
        point.id === id ? { ...point, [field]: value } : point
      )
    );
  };

  // Delete an insertion point
  const deleteInsertionPoint = (id: string) => {
    onInsertionPointsChange(insertionPoints.filter(point => point.id !== id));
  };

  // Assign B-roll to an insertion point
  const assignBRoll = (insertionPointId: string, bRollId: string) => {
    onInsertionPointsChange(
      insertionPoints.map(point => 
        point.id === insertionPointId ? { ...point, bRollId } : point
      )
    );
    setSelectedBRoll(null);
  };

  return (
    <div className={`${className}`}>
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">B-Roll Management</h3>
        
        {/* Tabs */}
        <div className="border-b border-gray-200 mb-4">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('library')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'library'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              My Library
            </button>
            <button
              onClick={() => setActiveTab('suggestions')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'suggestions'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              AI Suggestions
            </button>
          </nav>
        </div>
        
        {activeTab === 'library' ? (
          <>
            {/* B-roll library */}
            <div className="mb-4">
              <div className="flex flex-col sm:flex-row gap-4 mb-4">
                <div className="flex-grow">
                  <input
                    type="text"
                    placeholder="Search B-roll..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="flex-shrink-0">
                  <select
                    value=""
                    onChange={(e) => {
                      const tag = e.target.value;
                      if (tag && !selectedTags.includes(tag)) {
                        setSelectedTags([...selectedTags, tag]);
                      }
                      e.target.value = '';
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Filter by tag</option>
                    {allTags.map((tag) => (
                      <option key={tag} value={tag}>
                        {tag}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              
              {/* Selected tags */}
              {selectedTags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => setSelectedTags(selectedTags.filter(t => t !== tag))}
                        className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full text-blue-400 hover:bg-blue-200 hover:text-blue-500 focus:outline-none"
                      >
                        <span className="sr-only">Remove tag</span>
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                      </button>
                    </span>
                  ))}
                  <button
                    type="button"
                    onClick={() => setSelectedTags([])}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    Clear all
                  </button>
                </div>
              )}
              
              {/* B-roll grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredBRoll.map((bRoll) => (
                  <div
                    key={bRoll.id}
                    className={`border rounded-lg overflow-hidden cursor-pointer transition-all ${
                      selectedBRoll === bRoll.id
                        ? 'border-blue-500 ring-2 ring-blue-500'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                    onClick={() => setSelectedBRoll(bRoll.id)}
                  >
                    <div className="relative h-32 bg-gray-100">
                      {bRoll.thumbnailUrl ? (
                        <Image
                          src={bRoll.thumbnailUrl}
                          alt={bRoll.title}
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full bg-gray-200">
                          <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                          </svg>
                        </div>
                      )}
                      <div className="absolute top-2 right-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                          {bRoll.duration}
                        </span>
                      </div>
                    </div>
                    <div className="p-3">
                      <h4 className="font-medium text-gray-900">{bRoll.title}</h4>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {bRoll.tags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Upload new B-roll */}
                <div className="border border-dashed border-gray-300 rounded-lg overflow-hidden">
                  <VideoUploader
                    onVideoSelected={onBRollUpload}
                    maxSizeMB={100}
                    className="h-full"
                  />
                </div>
              </div>
            </div>
          </>
        ) : (
          // AI Suggestions tab
          <div className="bg-gray-50 rounded-lg p-6 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">AI Suggestions</h3>
            <p className="mt-1 text-sm text-gray-500">
              Upload your main video first to get AI-powered B-roll suggestions based on your content.
            </p>
          </div>
        )}
      </div>
      
      {/* Insertion points */}
      <div className="mt-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Insertion Points</h3>
          <button
            onClick={addInsertionPoint}
            className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
            Add Insertion Point
          </button>
        </div>
        
        {insertionPoints.length === 0 ? (
          <div className="bg-gray-50 p-4 rounded-lg text-center">
            <p className="text-gray-500">No insertion points yet. Add one to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {insertionPoints.map((point) => {
              const assignedBRoll = bRollLibrary.find(br => br.id === point.bRollId);
              
              return (
                <div 
                  key={point.id}
                  className="border rounded-lg overflow-hidden"
                >
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-gray-900">
                        Insertion at {formatTime(point.timestamp)}
                      </h4>
                      <button
                        onClick={() => deleteInsertionPoint(point.id)}
                        className="text-red-600 hover:text-red-800"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                      </button>
                    </div>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Timestamp (seconds)
                        </label>
                        <input
                          type="number"
                          min="0"
                          step="0.1"
                          value={point.timestamp}
                          onChange={(e) => updateInsertionPoint(point.id, 'timestamp', parseFloat(e.target.value))}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Duration (seconds)
                        </label>
                        <input
                          type="number"
                          min="0.5"
                          step="0.1"
                          value={point.duration}
                          onChange={(e) => updateInsertionPoint(point.id, 'duration', parseFloat(e.target.value))}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                    
                    {assignedBRoll ? (
                      <div className="flex items-center justify-between bg-gray-50 p-2 rounded">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-gray-200 rounded overflow-hidden mr-2">
                            {assignedBRoll.thumbnailUrl ? (
                              <Image
                                src={assignedBRoll.thumbnailUrl}
                                alt={assignedBRoll.title}
                                width={40}
                                height={40}
                                className="object-cover"
                              />
                            ) : (
                              <div className="flex items-center justify-center h-full">
                                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                                </svg>
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">{assignedBRoll.title}</p>
                            <p className="text-xs text-gray-500">{assignedBRoll.duration}</p>
                          </div>
                        </div>
                        <button
                          onClick={() => updateInsertionPoint(point.id, 'bRollId', undefined)}
                          className="text-xs text-red-600 hover:text-red-800"
                        >
                          Remove
                        </button>
                      </div>
                    ) : (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-500">No B-roll assigned</span>
                        {selectedBRoll && (
                          <button
                            onClick={() => assignBRoll(point.id, selectedBRoll)}
                            className="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-blue-600 hover:bg-blue-700"
                          >
                            Assign Selected
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
