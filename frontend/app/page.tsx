'use client'

import { useState, useEffect } from 'react'
import { Upload, FileVideo, Download, Trash2, Play, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import axios from 'axios'

interface Project {
  id: string
  filename: string
  file_size: number
  status: string
  transcription?: any
  processed_video_path?: string
  created_at: string
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const [loading, setLoading] = useState(true)

  // Fetch projects on component mount
  useEffect(() => {
    fetchProjects()
    // Set up polling for project status updates
    const interval = setInterval(fetchProjects, 3000)
    return () => clearInterval(interval)
  }, [])

  const fetchProjects = async () => {
    try {
      const response = await axios.get('/api/v1/projects')
      setProjects(response.data.projects || [])  
      setLoading(false)
    } catch (error) {
      console.error('Error fetching projects:', error)
      setLoading(false)
    }
  }

  const handleFileUpload = async (file: File) => {
    if (!file.type.startsWith('video/')) {
      alert('Please select a video file')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('file', file)
    // Generate a project name from the filename
    const projectName = file.name.replace(/\.[^/.]+$/, '') // Remove file extension
    formData.append('project_name', projectName)

    try {
      const response = await axios.post('/api/v1/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setUploadProgress(progress)
          }
        },
      })

      // Start transcription automatically
      await axios.post('/api/v1/transcribe', {
        project_id: response.data.project_id
      })

      fetchProjects()
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Error uploading file. Please try again.')
    } finally {
      setUploading(false)
      setUploadProgress(0)
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
      await axios.delete(`/api/v1/projects/${projectId}`)
      fetchProjects()
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
              <Upload className="mx-auto w-12 h-12 text-gray-400" />
              <div>
                <p className="text-lg font-medium text-gray-700">
                  Drop your video here or click to browse
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Supports MP4, MOV, AVI and other video formats
                </p>
              </div>
              <label className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 cursor-pointer transition-colors">
                <FileVideo className="w-4 h-4 mr-2" />
                Choose Video File
                <input
                  type="file"
                  accept="video/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
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
