'use client'

import { useState } from 'react'
import { Upload, FileVideo, Download, Trash2, Play, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import axios from 'axios'
import { useProjects, useDeleteProject, useUploadProject, type Project } from '../hooks/use-projects'
import { useUploadStore } from '../store/upload-store'
import EnhancedUpload from '@/components/Enhancedupload'

export default function Home() {
  const { data: projectsData, isLoading: loading, error } = useProjects()
  const deleteProjectMutation = useDeleteProject()
  const uploadProjectMutation = useUploadProject()
  const { 
    uploading, 
    uploadProgress, 
    dragOver, 
    setUploading, 
    setUploadProgress, 
    setDragOver, 
    resetUpload 
  } = useUploadStore()
  
  const projects = projectsData?.projects || []


  const handleFileUpload = async (file: File) => {
    if (!file.type.startsWith('video/')) {
      alert('Please select a video file')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    const projectName = file.name.replace(/\.[^/.]+$/, '')

    try {
      await uploadProjectMutation.mutateAsync({
        file,
        projectName,
        onProgress: setUploadProgress
      })
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Error uploading file. Please try again.')
    } finally {
      resetUpload()
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const deleteProject = async (projectId: string) => {
    if (!confirm('Are you sure you want to delete this project?')) return

    try {
      await deleteProjectMutation.mutateAsync(projectId)
    } catch (error) {
      console.error('Error deleting project:', error)
      alert('Error deleting project. Please try again.')
    }
  }

  const downloadFile = async (projectId: string, type: 'srt' | 'video', processed = false) => {
    try {
      const url = type === 'srt' 
        ? `/api/v1/projects/${projectId}/download/srt`
        : `/api/v1/projects/${projectId}/download/video${processed ? '?processed=true' : ''}`
      
      const response = await axios.get(url, { responseType: 'blob' })
      
      const blob = new Blob([response.data])
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      
      const contentDisposition = response.headers['content-disposition']
      let filename = `download.${type === 'srt' ? 'srt' : 'mp4'}`
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/)
        if (match) filename = match[1]
      }
      
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
    } catch (error) {
      console.error('Error downloading file:', error)
      alert('Error downloading file. Please try again.')
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'processing':
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      default:
        return <Clock className="w-5 h-5 text-gray-400" />
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="px-4 py-6">
      {/* Upload Section */}
      <div className="mb-8">
        <div
          className={`upload-area rounded-lg p-8 text-center ${dragOver ? 'dragover' : ''}`}
          onDrop={handleDrop}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
        >
          {uploading ? (
            <div className="space-y-4">
              <div className="animate-spin mx-auto w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
              <p className="text-lg font-medium text-gray-700">Uploading video...</p>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full progress-bar"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-500">{uploadProgress}% complete</p>
            </div>
          ) : (
            <div className="space-y-4">
              <EnhancedUpload />
            
            </div>
          )}
        </div>
      </div>

      {/* Projects Section */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Your Projects</h2>
        
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin mx-auto w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            <p className="mt-2 text-gray-500">Loading projects...</p>
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileVideo className="mx-auto w-12 h-12 mb-4 text-gray-300" />
            <p>No projects yet. Upload a video to get started!</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {projects.map((project) => (
              <div key={project.id} className="bg-white rounded-lg shadow-sm border p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <FileVideo className="w-8 h-8 text-blue-500" />
                    <div>
                      <h3 className="font-medium text-gray-900">{project.filename}</h3>
                      <p className="text-sm text-gray-500">
                        {formatFileSize(project.file_size)} • {new Date(project.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(project.status)}
                      <span className="text-sm font-medium capitalize text-gray-700">
                        {project.status}
                      </span>
                    </div>
                    
                    {project.status === 'completed' && (
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => downloadFile(project.id, 'srt')}
                          className="inline-flex items-center px-3 py-1 bg-green-100 text-green-700 rounded-md hover:bg-green-200 transition-colors text-sm"
                        >
                          <Download className="w-4 h-4 mr-1" />
                          SRT
                        </button>
                        <button
                          onClick={() => downloadFile(project.id, 'video', false)}
                          className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 transition-colors text-sm"
                        >
                          <Download className="w-4 h-4 mr-1" />
                          Original
                        </button>
                        {project.processed_video_path && (
                          <button
                            onClick={() => downloadFile(project.id, 'video', true)}
                            className="inline-flex items-center px-3 py-1 bg-purple-100 text-purple-700 rounded-md hover:bg-purple-200 transition-colors text-sm"
                          >
                            <Play className="w-4 h-4 mr-1" />
                            With Captions
                          </button>
                        )}
                      </div>
                    )}
                    
                    <button
                      onClick={() => deleteProject(project.id)}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                {project.transcription && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium text-gray-900 mb-2">Transcription Preview</h4>
                    <p className="text-sm text-gray-600 line-clamp-3">
                      {project.transcription.segments?.slice(0, 3).map((seg: any) => seg.text).join(' ') || 'Transcription available'}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
