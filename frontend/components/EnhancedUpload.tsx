// components/EnhancedUpload.tsx
'use client'

import { useState, useCallback, useRef } from 'react'
import { Upload, FileVideo, X, Pause, Play, AlertCircle, Settings, Wand2 } from 'lucide-react'
import { useChunkedUpload } from '../hooks/use-chunked-upload'
import { useQueryClient } from '@tanstack/react-query'

interface UploadProgress {
  filename: string
  progress: number
  chunkProgress?: string
  status: 'uploading' | 'paused' | 'error' | 'completed'
  error?: string
  canCancel: boolean
}

interface ProcessingOptions {
  enableIntelligentEditing: boolean
  editingStyle: 'engaging' | 'professional' | 'educational' | 'social_media'
  targetDuration: number
  contentType: 'general' | 'tutorial' | 'interview' | 'presentation' | 'vlog'
}

export default function EnhancedUpload() {
  const [dragOver, setDragOver] = useState(false)
  const [uploads, setUploads] = useState<Map<string, UploadProgress>>(new Map())
  const [showOptions, setShowOptions] = useState(false)
  const [processingOptions, setProcessingOptions] = useState<ProcessingOptions>({
    enableIntelligentEditing: false,
    editingStyle: 'engaging',
    targetDuration: 60,
    contentType: 'general'
  })
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  
  const { uploadFile } = useChunkedUpload()

  const startUpload = useCallback(async (file: File) => {
    const uploadId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const projectName = file.name.replace(/\.[^/.]+$/, '')

    // Add to uploads map
    setUploads(prev => new Map(prev.set(uploadId, {
      filename: file.name,
      progress: 0,
      status: 'uploading',
      canCancel: true
    })))

    try {
      await uploadFile(file, projectName, {
        chunkSize: 5 * 1024 * 1024, // 5MB chunks
        processingOptions, // Pass processing options
        onProgress: (progress) => {
          setUploads(prev => {
            const updated = new Map(prev)
            const current = updated.get(uploadId)
            if (current) {
              updated.set(uploadId, {
                ...current,
                progress,
                status: progress === 100 ? 'completed' : 'uploading'
              })
            }
            return updated
          })
        },
        onChunkProgress: (current, total) => {
          setUploads(prev => {
            const updated = new Map(prev)
            const currentUpload = updated.get(uploadId)
            if (currentUpload) {
              updated.set(uploadId, {
                ...currentUpload,
                chunkProgress: `${current}/${total} chunks`
              })
            }
            return updated
          })
        }
      })

      // Upload completed successfully
      setUploads(prev => {
        const updated = new Map(prev)
        const current = updated.get(uploadId)
        if (current) {
          updated.set(uploadId, {
            ...current,
            status: 'completed',
            progress: 100,
            canCancel: false
          })
        }
        return updated
      })

      // Refresh projects list
      queryClient.invalidateQueries({ queryKey: ['projects'] })

      // Auto-remove completed upload after 3 seconds
      setTimeout(() => {
        setUploads(prev => {
          const updated = new Map(prev)
          updated.delete(uploadId)
          return updated
        })
      }, 3000)

    } catch (error) {
      // Upload failed
      setUploads(prev => {
        const updated = new Map(prev)
        const current = updated.get(uploadId)
        if (current) {
          updated.set(uploadId, {
            ...current,
            status: 'error',
            error: error instanceof Error ? error.message : 'Upload failed',
            canCancel: false
          })
        }
        return updated
      })
    }
  }, [uploadFile, queryClient, processingOptions])

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return

    Array.from(files).forEach(file => {
      // Validate file type
      if (!file.type.startsWith('video/')) {
        alert(`${file.name} is not a video file`)
        return
      }

      // Validate file size (2GB limit)
      const maxSize = 2 * 1024 * 1024 * 1024
      if (file.size > maxSize) {
        alert(`${file.name} is too large. Maximum size is 2GB`)
        return
      }

      startUpload(file)
    })
  }, [startUpload])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }, [handleFileSelect])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileSelect(e.target.files)
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [handleFileSelect])

  const cancelUpload = useCallback(async (uploadId: string) => {
    try {
      await fetch(`/api/v1/upload/${uploadId}`, { method: 'DELETE' })
      setUploads(prev => {
        const updated = new Map(prev)
        updated.delete(uploadId)
        return updated
      })
    } catch (error) {
      console.error('Failed to cancel upload:', error)
    }
  }, [])

  const retryUpload = useCallback((uploadId: string) => {
    // Remove the failed upload and trigger file input
    setUploads(prev => {
      const updated = new Map(prev)
      updated.delete(uploadId)
      return updated
    })
    fileInputRef.current?.click()
  }, [])

  const getStatusColor = (status: UploadProgress['status']) => {
    switch (status) {
      case 'uploading': return 'text-blue-600'
      case 'completed': return 'text-green-600'
      case 'error': return 'text-red-600'
      case 'paused': return 'text-yellow-600'
      default: return 'text-gray-600'
    }
  }

  const getStatusIcon = (status: UploadProgress['status']) => {
    switch (status) {
      case 'uploading': return <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
      case 'completed': return <div className="w-4 h-4 bg-green-500 rounded-full flex items-center justify-center"><span className="text-white text-xs">✓</span></div>
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'paused': return <Pause className="w-4 h-4 text-yellow-500" />
      default: return null
    }
  }

  return (
    <div className="space-y-4">
      {/* Processing Options */}
      <div className="bg-white border rounded-lg p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 flex items-center">
            <Settings className="w-4 h-4 mr-2" />
            Processing Options
          </h3>
          <button
            onClick={() => setShowOptions(!showOptions)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {showOptions ? 'Hide' : 'Show'} Options
          </button>
        </div>

        {/* Toggle for intelligent editing */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg mb-3">
          <div className="flex items-center space-x-3">
            <Wand2 className={`w-5 h-5 ${processingOptions.enableIntelligentEditing ? 'text-purple-600' : 'text-gray-400'}`} />
            <div>
              <p className="font-medium text-gray-900">Intelligent Video Editing</p>
              <p className="text-sm text-gray-500">
                {processingOptions.enableIntelligentEditing 
                  ? 'Create highlights + add captions' 
                  : 'Just add captions to full video'
                }
              </p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={processingOptions.enableIntelligentEditing}
              onChange={(e) => setProcessingOptions(prev => ({
                ...prev,
                enableIntelligentEditing: e.target.checked
              }))}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        {/* Advanced options (shown when intelligent editing is enabled) */}
        {showOptions && processingOptions.enableIntelligentEditing && (
          <div className="space-y-4 border-t pt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Editing Style */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Editing Style
                </label>
                <select
                  value={processingOptions.editingStyle}
                  onChange={(e) => setProcessingOptions(prev => ({
                    ...prev,
                    editingStyle: e.target.value as ProcessingOptions['editingStyle']
                  }))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="engaging">Engaging (Fast-paced)</option>
                  <option value="professional">Professional (Polished)</option>
                  <option value="educational">Educational (Clear)</option>
                  <option value="social_media">Social Media (Viral)</option>
                </select>
              </div>

              {/* Content Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Content Type
                </label>
                <select
                  value={processingOptions.contentType}
                  onChange={(e) => setProcessingOptions(prev => ({
                    ...prev,
                    contentType: e.target.value as ProcessingOptions['contentType']
                  }))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="general">General</option>
                  <option value="tutorial">Tutorial/How-to</option>
                  <option value="interview">Interview/Podcast</option>
                  <option value="presentation">Presentation</option>
                  <option value="vlog">Vlog/Personal</option>
                </select>
              </div>
            </div>

            {/* Target Duration */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Duration (seconds): {processingOptions.targetDuration}s
              </label>
              <input
                type="range"
                min="30"
                max="300"
                step="15"
                value={processingOptions.targetDuration}
                onChange={(e) => setProcessingOptions(prev => ({
                  ...prev,
                  targetDuration: parseInt(e.target.value)
                }))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>30s</span>
                <span>2min</span>
                <span>5min</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Upload Area */}
      <div
        className={`upload-area rounded-lg p-8 text-center border-2 border-dashed transition-colors ${
          dragOver 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
      >
        <Upload className="mx-auto w-12 h-12 text-gray-400 mb-4" />
        <div className="space-y-2">
          <p className="text-lg font-medium text-gray-700">
            Drop your videos here or click to browse
          </p>
          <p className="text-sm text-gray-500">
            Supports MP4, MOV, AVI, WebM • Max 2GB per file
          </p>
          <div className="space-y-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              <FileVideo className="w-4 h-4 mr-2" />
              Choose Video Files
            </button>
            <p className="text-xs text-gray-400">
              {processingOptions.enableIntelligentEditing 
                ? `Will create ${Math.floor(processingOptions.targetDuration / 60)}:${(processingOptions.targetDuration % 60).toString().padStart(2, '0')} highlight video with captions`
                : 'Will add captions to the full video'
              }
            </p>
          </div>
        </div>
        
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          multiple
          onChange={handleInputChange}
          className="hidden"
        />
      </div>

      {/* Active Uploads */}
      {uploads.size > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-gray-900">Active Uploads</h3>
          
          {Array.from(uploads.entries()).map(([uploadId, upload]) => (
            <div key={uploadId} className="bg-white border rounded-lg p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(upload.status)}
                  <div>
                    <p className="font-medium text-gray-900 truncate max-w-xs">
                      {upload.filename}
                    </p>
                    <p className="text-sm text-gray-500">
                      {upload.chunkProgress && upload.status === 'uploading' && (
                        <span>{upload.chunkProgress} • </span>
                      )}
                      <span className={getStatusColor(upload.status)}>
                        {upload.status === 'uploading' && 'Uploading...'}
                        {upload.status === 'completed' && 'Upload complete'}
                        {upload.status === 'error' && upload.error}
                        {upload.status === 'paused' && 'Paused'}
                      </span>
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {upload.status === 'error' && (
                    <button
                      onClick={() => retryUpload(uploadId)}
                      className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                    >
                      Retry
                    </button>
                  )}
                  
                  {upload.canCancel && (
                    <button
                      onClick={() => cancelUpload(uploadId)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              
              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    upload.status === 'error' 
                      ? 'bg-red-500' 
                      : upload.status === 'completed'
                      ? 'bg-green-500'
                      : 'bg-blue-500'
                  }`}
                  style={{ width: `${upload.progress}%` }}
                />
              </div>
              
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{Math.round(upload.progress)}%</span>
                {upload.status === 'uploading' && (
                  <span>Processing in chunks for reliability</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}