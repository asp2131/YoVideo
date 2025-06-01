"use client";

import MainLayout from '../../../components/layout/MainLayout';
import Link from 'next/link';
import { useEffect, useState, useRef, use } from 'react';
import { projectsApi, videosApi, Project, Video } from '../../../utils/api';

interface ProjectDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function ProjectDetailPage(props: ProjectDetailPageProps) {
  const resolvedParams = use(props.params);
  const { id } = resolvedParams;
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State for project and videos
  const [project, setProject] = useState<Project | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  
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
      await videosApi.uploadFile(uploadData.upload_url, file, id, uploadData.source_video_id);
      
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
        storage_path: selectedVideo.storage_path || '',
        original_filename: selectedVideo.original_filename || '',
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

  // Handle caption overlay processing
  const handleProcessCaptions = async () => {
    if (!selectedVideo) return;
    
    setIsProcessing(true);
    try {
      await videosApi.processCaptions(id, selectedVideo.id);
      
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
      console.error('Failed to process captions:', err);
      setError('Failed to process captions. Please try again.');
      setIsProcessing(false);
    }
  };

  // Handle downloading processed video
  const handleDownloadProcessedVideo = async () => {
    if (!selectedVideo || !selectedVideo.processed_video_path) return;
    
    try {
      const processedData = await videosApi.getProcessedVideo(id, selectedVideo.id);
      if (processedData.download_url) {
        window.open(processedData.download_url, '_blank');
      }
    } catch (err) {
      console.error('Failed to get download URL:', err);
      setError('Failed to get download URL. Please try again.');
    }
  };
  
  if (loading) {
    return (
      <MainLayout>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      </MainLayout>
    );
  }
  
  return (
    <MainLayout>
      <div className="py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <Link href="/" className="text-blue-600 hover:text-blue-800 text-sm mb-2 inline-block">
              ← Back to Projects
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">{project?.name || 'Project'}</h1>
          </div>
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg flex items-center"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
            {isUploading ? 'Uploading...' : 'Upload Video'}
          </button>
          <input 
            ref={fileInputRef}
            type="file" 
            accept="video/*" 
            onChange={handleFileUpload}
            className="hidden" 
          />
        </div>
        
        {/* Error Message */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        
        {/* Upload Progress */}
        {isUploading && (
          <div className="bg-white shadow rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <div className="flex-1">
                <div className="bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
              <span className="ml-4 text-sm text-gray-600">{uploadProgress}%</span>
            </div>
          </div>
        )}
        
        {/* Content */}
        {videos.length === 0 ? (
          <div className="bg-gray-50 rounded-lg p-8 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No videos uploaded</h3>
            <p className="mt-1 text-sm text-gray-500">Upload a video to start transcribing and adding captions.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Video List */}
              <div className="lg:col-span-1">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Videos</h2>
                <div className="space-y-2">
                  {videos.map((video) => (
                    <button
                      key={video.id}
                      onClick={() => setSelectedVideo(video)}
                      className={`w-full text-left p-3 rounded-lg border ${
                        selectedVideo?.id === video.id 
                          ? 'border-blue-500 bg-blue-50' 
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium text-gray-900">{video.original_filename || 'Untitled Video'}</div>
                      <div className="text-sm text-gray-500 mt-1">
                        Status: {video.transcription_status || 'pending'}
                      </div>
                      {video.processed_video_path && (
                        <div className="text-sm text-green-600 mt-1">
                          ✓ Captions processed
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Video Details */}
              <div className="lg:col-span-2">
                {selectedVideo ? (
                  <div className="bg-white shadow rounded-lg p-6">
                    <div className="flex justify-between items-start mb-4">
                      <h2 className="text-lg font-medium text-gray-900">
                        {selectedVideo.original_filename || 'Video Details'}
                      </h2>
                      <div className="space-x-2">
                        {selectedVideo.transcription_status !== 'transcription_completed' && (
                          <button 
                            onClick={handleTriggerTranscription}
                            disabled={isProcessing}
                            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1 px-3 rounded"
                          >
                            {isProcessing ? 'Processing...' : 'Trigger Transcription'}
                          </button>
                        )}
                        {selectedVideo.transcription_status === 'transcription_completed' && !selectedVideo.processed_video_path && (
                          <button 
                            onClick={handleProcessCaptions}
                            disabled={isProcessing}
                            className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium py-1 px-3 rounded"
                          >
                            {isProcessing ? 'Processing...' : 'Add Captions'}
                          </button>
                        )}
                        {selectedVideo.processed_video_path && (
                          <button 
                            onClick={handleDownloadProcessedVideo}
                            className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium py-1 px-3 rounded"
                          >
                            Download with Captions
                          </button>
                        )}
                      </div>
                    </div>
                    
                    {selectedVideo.transcription_status === 'transcription_completed' ? (
                      <div>
                        <div className="mb-6">
                          <h3 className="text-md font-medium text-gray-900 mb-2">Transcription</h3>
                          <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                            <p className="text-gray-700 whitespace-pre-wrap">
                              {typeof selectedVideo.transcription === 'string' 
                                ? selectedVideo.transcription 
                                : JSON.stringify(selectedVideo.transcription, null, 2)}
                            </p>
                          </div>
                        </div>
                        
                        {selectedVideo.processed_video_path && (
                          <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
                            <p className="text-green-800">
                              ✓ Video has been processed with captions. Click &quot;Download with Captions&quot; to get the final video.
                            </p>
                          </div>
                        )}
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
