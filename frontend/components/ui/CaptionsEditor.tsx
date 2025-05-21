import { useState, useEffect } from 'react';

interface Caption {
  id: string;
  text: string;
  startTime: number;
  endTime: number;
}

interface CaptionsEditorProps {
  captions: Caption[];
  onCaptionsChange: (captions: Caption[]) => void;
  currentVideoTime?: number;
  className?: string;
}

export default function CaptionsEditor({
  captions: initialCaptions,
  onCaptionsChange,
  currentVideoTime = 0,
  className = ''
}: CaptionsEditorProps) {
  const [captions, setCaptions] = useState<Caption[]>(initialCaptions);
  const [activeCaption, setActiveCaption] = useState<string | null>(null);
  const [editingCaption, setEditingCaption] = useState<string | null>(null);

  // Update active caption based on current video time
  useEffect(() => {
    if (captions.length === 0) return;

    const active = captions.find(
      caption => currentVideoTime >= caption.startTime && currentVideoTime <= caption.endTime
    );

    setActiveCaption(active?.id || null);
  }, [currentVideoTime, captions]);

  // Notify parent component when captions change
  useEffect(() => {
    onCaptionsChange(captions);
  }, [captions, onCaptionsChange]);

  // Format time (seconds to MM:SS.MS)
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  // Parse time string (MM:SS.MS to seconds)
  const parseTime = (timeString: string): number => {
    try {
      const [minutesSeconds, milliseconds] = timeString.split('.');
      const [minutes, seconds] = minutesSeconds.split(':');
      
      return (
        parseInt(minutes) * 60 + 
        parseInt(seconds) + 
        (milliseconds ? parseInt(milliseconds) / 1000 : 0)
      );
    } catch (error) {
      return 0;
    }
  };

  // Handle caption text change
  const handleCaptionTextChange = (id: string, newText: string) => {
    setCaptions(captions.map(caption => 
      caption.id === id ? { ...caption, text: newText } : caption
    ));
  };

  // Handle caption time change
  const handleCaptionTimeChange = (id: string, field: 'startTime' | 'endTime', timeString: string) => {
    const newTime = parseTime(timeString);
    
    setCaptions(captions.map(caption => {
      if (caption.id !== id) return caption;
      
      // Ensure start time is before end time
      if (field === 'startTime' && newTime >= caption.endTime) {
        return caption;
      }
      
      if (field === 'endTime' && newTime <= caption.startTime) {
        return caption;
      }
      
      return { ...caption, [field]: newTime };
    }));
  };

  // Add a new caption
  const addCaption = () => {
    const lastCaption = captions[captions.length - 1];
    const newStartTime = lastCaption ? lastCaption.endTime + 0.1 : 0;
    const newEndTime = newStartTime + 2; // Default 2-second caption
    
    const newCaption: Caption = {
      id: `caption-${Date.now()}`,
      text: 'New caption',
      startTime: newStartTime,
      endTime: newEndTime
    };
    
    setCaptions([...captions, newCaption]);
    setEditingCaption(newCaption.id);
  };

  // Delete a caption
  const deleteCaption = (id: string) => {
    setCaptions(captions.filter(caption => caption.id !== id));
    if (editingCaption === id) {
      setEditingCaption(null);
    }
  };

  // Split a caption at the current time
  const splitCaption = (id: string) => {
    const captionToSplit = captions.find(caption => caption.id === id);
    if (!captionToSplit || currentVideoTime <= captionToSplit.startTime || currentVideoTime >= captionToSplit.endTime) {
      return;
    }
    
    // Create two new captions
    const firstCaption: Caption = {
      id: `caption-${Date.now()}-1`,
      text: captionToSplit.text,
      startTime: captionToSplit.startTime,
      endTime: currentVideoTime
    };
    
    const secondCaption: Caption = {
      id: `caption-${Date.now()}-2`,
      text: captionToSplit.text,
      startTime: currentVideoTime,
      endTime: captionToSplit.endTime
    };
    
    // Replace the original caption with the two new ones
    setCaptions(
      captions.map(caption => 
        caption.id === id ? firstCaption : caption
      ).concat(secondCaption).sort((a, b) => a.startTime - b.startTime)
    );
  };

  // Merge with next caption
  const mergeWithNext = (id: string) => {
    const currentIndex = captions.findIndex(caption => caption.id === id);
    if (currentIndex === -1 || currentIndex === captions.length - 1) {
      return;
    }
    
    const currentCaption = captions[currentIndex];
    const nextCaption = captions[currentIndex + 1];
    
    const mergedCaption: Caption = {
      id: currentCaption.id,
      text: `${currentCaption.text} ${nextCaption.text}`,
      startTime: currentCaption.startTime,
      endTime: nextCaption.endTime
    };
    
    const newCaptions = [...captions];
    newCaptions.splice(currentIndex, 2, mergedCaption);
    setCaptions(newCaptions);
  };

  return (
    <div className={`${className}`}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Captions</h3>
        <button
          onClick={addCaption}
          className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
          </svg>
          Add Caption
        </button>
      </div>

      {captions.length === 0 ? (
        <div className="bg-gray-50 p-4 rounded-lg text-center">
          <p className="text-gray-500">No captions yet. Add a caption to get started.</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
          {captions.map((caption) => (
            <div 
              key={caption.id}
              className={`border rounded-lg overflow-hidden ${
                activeCaption === caption.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
              }`}
            >
              <div className="p-3">
                {editingCaption === caption.id ? (
                  <textarea
                    value={caption.text}
                    onChange={(e) => handleCaptionTextChange(caption.id, e.target.value)}
                    className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={2}
                    autoFocus
                  />
                ) : (
                  <p 
                    className="text-gray-800 cursor-pointer"
                    onClick={() => setEditingCaption(caption.id)}
                  >
                    {caption.text}
                  </p>
                )}
                
                <div className="flex items-center mt-2 text-sm">
                  <div className="flex-1 flex items-center">
                    <span className="text-gray-500 mr-1">Start:</span>
                    <input
                      type="text"
                      value={formatTime(caption.startTime)}
                      onChange={(e) => handleCaptionTimeChange(caption.id, 'startTime', e.target.value)}
                      className="w-24 p-1 border border-gray-300 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div className="flex-1 flex items-center">
                    <span className="text-gray-500 mr-1">End:</span>
                    <input
                      type="text"
                      value={formatTime(caption.endTime)}
                      onChange={(e) => handleCaptionTimeChange(caption.id, 'endTime', e.target.value)}
                      className="w-24 p-1 border border-gray-300 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div className="flex-1 flex justify-end space-x-1">
                    <button
                      onClick={() => splitCaption(caption.id)}
                      className="p-1 text-gray-500 hover:text-blue-600"
                      title="Split at current time"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"></path>
                      </svg>
                    </button>
                    <button
                      onClick={() => mergeWithNext(caption.id)}
                      className="p-1 text-gray-500 hover:text-blue-600"
                      title="Merge with next"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
                      </svg>
                    </button>
                    <button
                      onClick={() => deleteCaption(caption.id)}
                      className="p-1 text-gray-500 hover:text-red-600"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex justify-between">
        <button
          onClick={() => {
            // Sort captions by start time
            setCaptions([...captions].sort((a, b) => a.startTime - b.startTime));
          }}
          className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          Sort by Time
        </button>
        <button
          onClick={() => {
            // Fix overlapping captions
            const sortedCaptions = [...captions].sort((a, b) => a.startTime - b.startTime);
            
            for (let i = 0; i < sortedCaptions.length - 1; i++) {
              const current = sortedCaptions[i];
              const next = sortedCaptions[i + 1];
              
              if (current.endTime > next.startTime) {
                // Adjust the end time of the current caption
                current.endTime = next.startTime - 0.01;
              }
            }
            
            setCaptions(sortedCaptions);
          }}
          className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          Fix Overlaps
        </button>
      </div>
    </div>
  );
}
