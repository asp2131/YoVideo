"use client";

import MainLayout from '../../../components/layout/MainLayout';
import Link from 'next/link';
import { useEffect, useState, useRef } from 'react';
import { projectsApi, videosApi, Project, Video, Highlight } from '../../../utils/api';

interface ProjectDetailPageProps {
  params: {
    id: string;
  };
}

export default function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const { id } = params;
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State for project and videos
  const [project, setProject] = useState<Project | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  
  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Fetch project and videos
  useEffect(() => {
    const fetchProjectData = async () => {
      try {
        setLoading(true);
        // Fetch project details
        const projectData = await projectsApi.getProject(id);
        setProject(projectData);
        
        // Fetch videos for this project
        const videosData = await videosApi.getVideos(id);
        setVideos(videosData);
        
        // Select the first video if available
        if (videosData.length > 0) {
          setSelectedVideo(videosData[0]);
        }
        
        setError(null);
      } catch (err) {
        console.error('Failed to fetch project data:', err);
        setError('Failed to load project data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchProjectData();
  }, [id]);
  
  // Fetch highlights when a video is selected
  useEffect(() => {
    const fetchHighlights = async () => {
      if (!selectedVideo) return;
      
      try {
        // Only fetch highlights if transcription is completed
        if (selectedVideo.transcription_status === 'transcription_completed') {
          const highlightsData = await videosApi.getHighlights(id, selectedVideo.id);
          setHighlights(highlightsData);
        } else {
          setHighlights([]);
        }
      } catch (err) {
        console.error('Failed to fetch highlights:', err);
      }
    };
    
    fetchHighlights();
  }, [id, selectedVideo]);

  // Handle file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    setIsUploading(true);
    setUploadProgress(0);
    
    try {
      // Step 1: Initiate upload
      const uploadData = await videosApi.initiateUpload(id, {
        file_name: file.name,
        content_type: file.type,
      });
      
      // Step 2: Upload file to storage
      await videosApi.uploadFile(uploadData.upload_url, file, file.type);
      
      // Step 3: Trigger transcription
      await videosApi.triggerTranscription(id, uploadData.source_video_id, {
        storage_path: uploadData.storage_path,
        original_filename: file.name,
      });
      
      // Step 4: Refresh videos list
      const updatedVideos = await videosApi.getVideos(id);
      setVideos(updatedVideos);
      
      // Select the newly uploaded video
      const newVideo = updatedVideos.find(v => v.id === uploadData.source_video_id);
      if (newVideo) {
        setSelectedVideo(newVideo);
      }
      
      setIsUploading(false);
      setUploadProgress(100);
    } catch (err) {
      console.error('Failed to upload video:', err);
      setError('Failed to upload video. Please try again.');
      setIsUploading(false);
    }
  };
  
  // Handle triggering transcription manually
  const handleTriggerTranscription = async () => {
    if (!selectedVideo) return;
    
    setIsProcessing(true);
    
    try {
      await videosApi.triggerTranscription(id, selectedVideo.id, {
        storage_path: selectedVideo.storage_path,
        original_filename: selectedVideo.title,
      });
      
      // Refresh video data
      const updatedVideos = await videosApi.getVideos(id);
      setVideos(updatedVideos);
      
      // Update selected video
      const updatedVideo = updatedVideos.find(v => v.id === selectedVideo.id);
      if (updatedVideo) {
        setSelectedVideo(updatedVideo);
      }
      
      setIsProcessing(false);
    } catch (err) {
      console.error('Failed to trigger transcription:', err);
      setError('Failed to trigger transcription. Please try again.');
      setIsProcessing(false);
    }
  };

  return (
    <MainLayout>
      <div className="py-8">
        <div className="mb-6">
          <Link href="/" className="text-blue-600 hover:text-blue-800 flex items-center">
            <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
            </svg>
            Back to Projects
          </Link>
        </div>
        
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : error ? (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        ) : (
          <>
            <div className="flex justify-between items-center mb-8">
              <h1 className="text-2xl font-bold text-gray-900">{project?.title || 'Project'}</h1>
              <div className="flex space-x-3">
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileUpload} 
                  accept="video/*" 
                  className="hidden" 
                />
                <button 
                  onClick={() => fileInputRef.current?.click()} 
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg flex items-center"
                  disabled={isUploading}
                >
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                  </svg>
                  Upload Video
                </button>
              </div>
            </div>

            {isUploading && (
              <div className="mb-6">
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${uploadProgress}%` }}></div>
                </div>
                <p className="text-sm text-gray-600 mt-2">Uploading video... {uploadProgress}%</p>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left sidebar - Video List */}
              <div className="lg:col-span-1">
                <div className="bg-white shadow rounded-lg p-6 mb-6">
                  <h2 className="text-lg font-medium text-gray-900 mb-4">Project Videos</h2>
                  
                  {videos.length > 0 ? (
                    <div className="space-y-4">
                      {videos.map((video) => (
                        <div 
                          key={video.id} 
                          className={`p-3 rounded-lg cursor-pointer ${selectedVideo?.id === video.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50'}`}
                          onClick={() => setSelectedVideo(video)}
                        >
                          <div className="flex justify-between items-start">
                            <div>
                              <h3 className="font-medium text-gray-900">{video.title}</h3>
                              <p className="text-sm text-gray-500">{new Date(video.created_at).toLocaleDateString()}</p>
                            </div>
                            <div className="ml-2">
                              {video.transcription_status === 'transcription_completed' ? (
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  Transcribed
                                </span>
                              ) : video.transcription_status === 'pending_transcription' ? (
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                  Pending
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                  Not Transcribed
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-gray-500">No videos yet. Upload your first video.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Main content - Video Player and Transcription */}
              <div className="lg:col-span-2">
                {selectedVideo ? (
                  <div className="bg-white shadow rounded-lg p-6 mb-6">
                    <h2 className="text-lg font-medium text-gray-900 mb-4">{selectedVideo.title}</h2>
                    
                    <div className="aspect-w-16 aspect-h-9 bg-black rounded-lg mb-6">
                      {/* Video player would go here */}
                      <div className="flex items-center justify-center h-64 bg-gray-800 text-white">
                        Video Player Placeholder
                      </div>
                    </div>
                    
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-md font-medium text-gray-900">Transcription Status</h3>
                      {selectedVideo.transcription_status !== 'transcription_completed' && (
                        <button 
                          onClick={handleTriggerTranscription}
                          disabled={isProcessing}
                          className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1 px-3 rounded"
                        >
                          {isProcessing ? 'Processing...' : 'Trigger Transcription'}
                        </button>
                      )}
                    </div>
                    
                    {selectedVideo.transcription_status === 'transcription_completed' ? (
                      <div>
                        <div className="mb-6">
                          <h3 className="text-md font-medium text-gray-900 mb-2">Transcription</h3>
                          <div className="bg-gray-50 p-4 rounded-lg">
                            <p className="text-gray-700">{typeof selectedVideo.transcription === 'string' ? selectedVideo.transcription : 'Transcription data available'}</p>
                          </div>
                        </div>
                        
                        <div>
                          <h3 className="text-md font-medium text-gray-900 mb-2">Highlights</h3>
                          {highlights.length > 0 ? (
                            <div className="space-y-3">
                              {highlights.map((highlight, index) => (
                                <div key={index} className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
                                  <p className="text-gray-700">{highlight.text}</p>
                                  <div className="flex justify-between text-sm text-gray-500 mt-2">
                                    <span>Start: {highlight.start_time}s</span>
                                    <span>End: {highlight.end_time}s</span>
                                    <span>Score: {highlight.score}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="bg-gray-50 p-4 rounded-lg text-center">
                              <p className="text-gray-500">No highlights detected for this video.</p>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="bg-gray-50 p-4 rounded-lg text-center">
                        <p className="text-gray-500">
                          {selectedVideo.transcription_status === 'pending_transcription' 
                            ? 'Transcription in progress. This may take a few minutes.'
                            : 'Video has not been transcribed yet. Click "Trigger Transcription" to start.'}
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-white shadow rounded-lg p-6 mb-6 flex items-center justify-center h-64">
                    <div className="text-center">
                      <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                      </svg>
                      <h3 className="mt-2 text-sm font-medium text-gray-900">No video selected</h3>
                      <p className="mt-1 text-sm text-gray-500">Select a video from the list or upload a new one.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
}
