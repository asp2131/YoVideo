/**
 * API client for interacting with the VideoThingy API Gateway
 */

const API_BASE_URL = 'http://localhost:8080/api/v1';

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  thumbnail_url?: string;
  updated_at?: string;
}

export interface Video {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  storage_path: string;
  transcription_status?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TranscriptionData {
  segments: TranscriptSegment[];
}

export interface TranscriptSegment {
  text: string;
  start_time: number;
  end_time: number;
}

export interface Highlight {
  text: string;
  start_time: number;
  end_time: number;
  score: number;
}

/**
 * Project API methods
 */
export const projectsApi = {
  // Get all projects
  getProjects: async (): Promise<Project[]> => {
    const response = await fetch(`${API_BASE_URL}/projects`);
    if (!response.ok) {
      throw new Error(`Failed to fetch projects: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data || [];
  },

  // Get a single project by ID
  getProject: async (projectId: string): Promise<Project> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch project: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data;
  },

  // Create a new project
  createProject: async (projectData: { name: string; description?: string }): Promise<Project> => {
    const response = await fetch(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(projectData),
    });
    if (!response.ok) {
      throw new Error(`Failed to create project: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data;
  },

  // Delete a project
  deleteProject: async (projectId: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Failed to delete project: ${response.statusText}`);
    }
  },
};

/**
 * Video API methods
 */
export const videosApi = {
  // Get all videos for a project
  getVideos: async (projectId: string): Promise<Video[]> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos`);
    if (!response.ok) {
      throw new Error(`Failed to fetch videos: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data || [];
  },

  // Get a single video by ID
  getVideo: async (projectId: string, videoId: string): Promise<Video> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/${videoId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch video: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data;
  },

  // Initiate video upload
  initiateUpload: async (projectId: string, fileData: { file_name: string; content_type: string }): Promise<{ upload_url: string; source_video_id: string; storage_path: string }> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/initiate-upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(fileData),
    });
    if (!response.ok) {
      throw new Error(`Failed to initiate upload: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data;
  },

  // Upload video file to storage through our API Gateway to avoid CORS issues
  uploadFile: async (uploadUrl: string, file: File, projectId?: string, videoId?: string): Promise<void> => {
    // If projectId and videoId are not provided, try to extract them from the upload URL
    // This is for backward compatibility
    if (!projectId || !videoId) {
      const urlParts = uploadUrl.split('/');
      videoId = urlParts[urlParts.length - 2]; // Get the video ID from the URL
      
      // We don't want to use 'source-videos' as the projectId
      // Instead, use the actual project ID from the context
      // For now, we'll extract it from the URL, but this should be provided directly
      projectId = urlParts[urlParts.length - 4]; // Get the project ID from the URL
    }
    
    // Create a FormData object to send the file
    const formData = new FormData();
    formData.append('file', file);
    
    console.log(`Uploading file to API Gateway for project ${projectId}, video ${videoId}`);
    
    // Use our API Gateway endpoint instead of direct Supabase storage
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/${videoId}/upload`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Failed to upload file: ${response.statusText}`);
    }
  },

  // Trigger video transcription
  triggerTranscription: async (projectId: string, videoId: string, data: { storage_path: string; original_filename: string }): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/${videoId}/trigger-transcription`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`Failed to trigger transcription: ${response.statusText}`);
    }
  },

  // Get video transcription
  getTranscription: async (projectId: string, videoId: string): Promise<TranscriptionData> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/${videoId}/transcription`);
    if (!response.ok) {
      throw new Error(`Failed to fetch transcription: ${response.statusText}`);
    }
    const data = await response.json();
    return data.data;
  },

  // Get video highlights
  getHighlights: async (projectId: string, videoId: string): Promise<Highlight[]> => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/videos/${videoId}/highlights`);
    if (!response.ok) {
      throw new Error(`Failed to fetch highlights: ${response.statusText}`);
    }
    const data = await response.json();
    return data.highlights || [];
  },
};
