// hooks/use-projects.ts (updated)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

export interface ProcessingOptions {
  enable_intelligent_editing?: boolean
  editing_style?: 'engaging' | 'professional' | 'educational' | 'social_media'
  target_duration?: number
  content_type?: 'general' | 'tutorial' | 'interview' | 'presentation' | 'vlog'
}

export interface Project {
  id: string
  filename: string
  file_size: number
  status: string
  transcription?: any
  processed_video_path?: string
  processing_options?: ProcessingOptions
  created_at: string
  original_filename?: string
  video_path?: string
}

interface ProjectsResponse {
  projects: Project[]
}

export const useProjects = () => {
  return useQuery<ProjectsResponse>({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await axios.get('/api/v1/projects')
      return response.data
    },
    refetchInterval: 5000, // Poll every 5 seconds for status updates
  })
}

export const useDeleteProject = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (projectId: string) => {
      await axios.delete(`/api/v1/projects/${projectId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export const useUploadProject = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ 
      file, 
      projectName, 
      onProgress 
    }: { 
      file: File
      projectName: string
      onProgress?: (progress: number) => void 
    }) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('project_name', projectName)

      const response = await axios.post('/api/v1/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress(progress)
          }
        },
      })

      // Start transcription automatically
      await axios.post('/api/v1/transcribe', {
        project_id: response.data.project_id
      })

      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export const useReprocessProject = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ 
      projectId, 
      processingOptions 
    }: { 
      projectId: string
      processingOptions: {
        enableIntelligentEditing: boolean
        editingStyle: 'engaging' | 'professional' | 'educational' | 'social_media'
        targetDuration: number
        contentType: 'general' | 'tutorial' | 'interview' | 'presentation' | 'vlog'
      }
    }) => {
      const response = await axios.post(`/api/v1/projects/${projectId}/process`, processingOptions)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}