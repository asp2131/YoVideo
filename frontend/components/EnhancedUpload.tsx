// components/EnhancedUpload.tsx - Complete Fixed Version
'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Upload, FileVideo, X, Pause, Play, AlertCircle, Settings, Wand2, Info, Sparkles, Clock, CheckCircle } from 'lucide-react'
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
  const [isClient, setIsClient] = useState(false)
  const [processingOptions, setProcessingOptions] = useState<ProcessingOptions>({
    enableIntelligentEditing: false,
    editingStyle: 'engaging',
    targetDuration: 60,
    contentType: 'general'
  })
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  
  const { uploadFile } = useChunkedUpload()

  // Fix hydration issues
  useEffect(() => {
    setIsClient(true)
  }, [])

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
      // Log processing options for debugging
      console.log('🚀 Starting upload with processing options:', processingOptions)
      console.log('🤖 Intelligent editing enabled:', processingOptions.enableIntelligentEditing)

      await uploadFile(file, projectName, {
        chunkSize: 5 * 1024 * 1024, // 5MB chunks
        processingOptions: {
          // Send both formats to ensure backend compatibility
          enable_intelligent_editing: processingOptions.enableIntelligentEditing,
          enableIntelligentEditing: processingOptions.enableIntelligentEditing,
          editing_style: processingOptions.editingStyle,
          editingStyle: processingOptions.editingStyle,
          target_duration: processingOptions.targetDuration,
          targetDuration: processingOptions.targetDuration,
          content_type: processingOptions.contentType,
          contentType: processingOptions.contentType
        },
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

      // Auto-remove completed upload after delay (longer for intelligent editing)
      const autoRemoveDelay = processingOptions.enableIntelligentEditing ? 10000 : 5000
      setTimeout(() => {
        setUploads(prev => {
          const updated = new Map(prev)
          updated.delete(uploadId)
          return updated
        })
      }, autoRemoveDelay)

    } catch (error) {
      console.error('❌ Upload failed:', error)
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
    if (!isClient) return null // Prevent hydration issues
    
    switch (status) {
      case 'uploading': return <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'paused': return <Pause className="w-4 h-4 text-yellow-500" />
      default: return null
    }
  }

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const getEditingStyleIcon = (style: string) => {
    switch (style) {
      case 'engaging': return '🔥'
      case 'professional': return '💼'
      case 'educational': return '📚'
      case 'social_media': return '📱'
      default: return '🎬'
    }
  }

  const getContentTypeIcon = (type: string) => {
    switch (type) {
      case 'tutorial': return '🎯'
      case 'interview': return '🎤'
      case 'presentation': return '📊'
      case 'vlog': return '📝'
      default: return '🎬'
    }
  }

  return (
    <div className="space-y-4">
      {/* Only render full UI after client hydration */}
      {!isClient ? (
        <div className="bg-white border rounded-lg p-4 shadow-sm">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-3"></div>
            <div className="h-20 bg-gray-200 rounded mb-3"></div>
            <div className="h-40 bg-gray-200 rounded"></div>
          </div>
        </div>
      ) : (
        <>
          {/* Processing Options */}
          <div className="bg-white border rounded-lg p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 flex items-center">
            <Settings className="w-4 h-4 mr-2" />
            Processing Options
          </h3>
          <button
            onClick={() => setShowOptions(!showOptions)}
            className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
          >
            {showOptions ? 'Hide' : 'Show'} Advanced
          </button>
        </div>

        {/* Intelligent Editing Toggle */}
        <div className={`p-4 rounded-lg mb-3 border transition-all duration-300 ${
          processingOptions.enableIntelligentEditing 
            ? 'bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200 shadow-sm ring-1 ring-purple-100' 
            : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="relative">
                {processingOptions.enableIntelligentEditing ? (
                  <div className="relative">
                    <Sparkles className="w-6 h-6 text-purple-600" />
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-purple-500 rounded-full animate-ping"></div>
                  </div>
                ) : (
                  <Wand2 className="w-6 h-6 text-gray-400" />
                )}
              </div>
              <div>
                <p className="font-semibold text-gray-900 flex items-center">
                  Intelligent Video Editing
                  {processingOptions.enableIntelligentEditing && (
                    <span className="ml-2 px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full font-medium">
                      ✨ AI Enabled
                    </span>
                  )}
                </p>
                <p className="text-sm text-gray-600">
                  {processingOptions.enableIntelligentEditing 
                    ? `🎬 Create engaging ${formatDuration(processingOptions.targetDuration)} highlights with professional captions` 
                    : '📝 Add professional captions to full video'
                  }
                </p>
                {processingOptions.enableIntelligentEditing && (
                  <p className="text-xs text-purple-600 mt-1">
                    {getEditingStyleIcon(processingOptions.editingStyle)} {processingOptions.editingStyle} style • {getContentTypeIcon(processingOptions.contentType)} {processingOptions.contentType}
                  </p>
                )}
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={processingOptions.enableIntelligentEditing}
                onChange={(e) => {
                  const enabled = e.target.checked
                  console.log('🔄 Intelligent editing toggled:', enabled)
                  setProcessingOptions(prev => ({
                    ...prev,
                    enableIntelligentEditing: enabled
                  }))
                }}
                className="sr-only peer"
              />
              <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-purple-600 shadow-sm"></div>
            </label>
          </div>
        </div>

        {/* Info about intelligent editing */}
        {processingOptions.enableIntelligentEditing && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3 animate-in slide-in-from-top-2 duration-300">
            <div className="flex items-start space-x-2">
              <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">✨ What happens with intelligent editing:</p>
                <ul className="space-y-1 text-xs">
                  <li>• 🤖 AI analyzes your video content, audio, and speech patterns</li>
                  <li>• 🎯 Automatically detects engaging moments and highlights</li>
                  <li>• ✂️ Removes silent sections and low-energy segments</li>
                  <li>• 💬 Adds professional word-by-word animated captions</li>
                  <li>• 🎥 Outputs a shorter, more engaging video perfect for social media</li>
                  <li>• ⚡ Processing takes 2-5 minutes depending on video length</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Advanced options */}
        {showOptions && processingOptions.enableIntelligentEditing && (
          <div className="space-y-4 border-t pt-4 animate-in slide-in-from-top-2 duration-300">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Editing Style */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  🎨 Editing Style
                </label>
                <select
                  value={processingOptions.editingStyle}
                  onChange={(e) => {
                    const style = e.target.value as ProcessingOptions['editingStyle']
                    console.log('🎨 Editing style changed to:', style)
                    setProcessingOptions(prev => ({
                      ...prev,
                      editingStyle: style
                    }))
                  }}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-colors"
                >
                  <option value="engaging">🔥 Engaging (Fast-paced, dynamic cuts)</option>
                  <option value="professional">💼 Professional (Polished, clean editing)</option>
                  <option value="educational">📚 Educational (Clear, informative flow)</option>
                  <option value="social_media">📱 Social Media (Viral-ready, punchy)</option>
                </select>
              </div>

              {/* Content Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  📋 Content Type
                </label>
                <select
                  value={processingOptions.contentType}
                  onChange={(e) => {
                    const contentType = e.target.value as ProcessingOptions['contentType']
                    console.log('📋 Content type changed to:', contentType)
                    setProcessingOptions(prev => ({
                      ...prev,
                      contentType: contentType
                    }))
                  }}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-colors"
                >
                  <option value="general">🎬 General Content</option>
                  <option value="tutorial">🎯 Tutorial/How-to</option>
                  <option value="interview">🎤 Interview/Podcast</option>
                  <option value="presentation">📊 Presentation/Demo</option>
                  <option value="vlog">📝 Vlog/Personal Story</option>
                </select>
              </div>
            </div>

            {/* Target Duration */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                ⏱️ Target Duration: <span className="font-semibold text-purple-600">{formatDuration(processingOptions.targetDuration)}</span>
              </label>
              <input
                type="range"
                min="30"
                max="300"
                step="15"
                value={processingOptions.targetDuration}
                onChange={(e) => {
                  const duration = parseInt(e.target.value)
                  console.log('⏱️ Target duration changed to:', duration, 'seconds')
                  setProcessingOptions(prev => ({
                    ...prev,
                    targetDuration: duration
                  }))
                }}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, #9333ea 0%, #9333ea ${((processingOptions.targetDuration - 30) / 270) * 100}%, #d1d5db ${((processingOptions.targetDuration - 30) / 270) * 100}%, #d1d5db 100%)`
                }}
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>30s</span>
                <span>2:30</span>
                <span>5:00</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Upload Area */}
      <div
        className={`upload-area rounded-lg p-8 text-center border-2 border-dashed transition-all duration-300 ${
          dragOver 
            ? 'border-purple-500 bg-purple-50 scale-[1.02] shadow-lg' 
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
        }`}
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
      >
        <div className="flex justify-center mb-4">
          {dragOver ? (
            <Sparkles className="w-12 h-12 text-purple-500 animate-bounce" />
          ) : (
            <Upload className="w-12 h-12 text-gray-400 transition-colors" />
          )}
        </div>
        <div className="space-y-2">
          <p className="text-lg font-medium text-gray-700">
            Drop your videos here or click to browse
          </p>
          <p className="text-sm text-gray-500">
            Supports MP4, MOV, AVI, WebM • Max 2GB per file
          </p>
          <div className="space-y-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-md hover:shadow-lg transform hover:scale-105"
            >
              <FileVideo className="w-4 h-4 mr-2" />
              Choose Video Files
            </button>
            <div className="text-xs text-gray-500 max-w-md mx-auto">
              {processingOptions.enableIntelligentEditing ? (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-2">
                  <p className="font-medium text-purple-800">🤖 AI Processing Enabled</p>
                  <p className="text-purple-700">
                    Will create {formatDuration(processingOptions.targetDuration)} highlights with {getEditingStyleIcon(processingOptions.editingStyle)} {processingOptions.editingStyle} style + professional captions
                  </p>
                </div>
              ) : (
                <p>📝 Will add professional captions to full video</p>
              )}
            </div>
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
          <h3 className="font-semibold text-gray-900 flex items-center">
            <span>Active Uploads</span>
            <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">
              {uploads.size}
            </span>
          </h3>
          
          {Array.from(uploads.entries()).map(([uploadId, upload]) => (
            <div key={uploadId} className="bg-white border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(upload.status)}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate max-w-xs">
                      {upload.filename}
                    </p>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      {upload.chunkProgress && upload.status === 'uploading' && (
                        <span className="text-blue-600 font-medium">{upload.chunkProgress}</span>
                      )}
                      <span className={getStatusColor(upload.status)}>
                        {upload.status === 'uploading' && '⬆️ Uploading...'}
                        {upload.status === 'completed' && (
                          <span className="flex items-center">
                            <CheckCircle className="w-4 h-4 mr-1" />
                            Upload complete - Processing started
                            {processingOptions.enableIntelligentEditing && (
                              <span className="ml-1 text-purple-600">🤖</span>
                            )}
                          </span>
                        )}
                        {upload.status === 'error' && `❌ ${upload.error}`}
                        {upload.status === 'paused' && '⏸️ Paused'}
                      </span>
                    </div>
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
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all duration-500 ${
                    upload.status === 'error' 
                      ? 'bg-red-500' 
                      : upload.status === 'completed'
                      ? 'bg-green-500'
                      : 'bg-gradient-to-r from-purple-500 to-blue-500'
                  }`}
                  style={{ width: `${upload.progress}%` }}
                />
              </div>
              
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{Math.round(upload.progress)}%</span>
                {upload.status === 'uploading' && (
                  <span>Reliable chunked upload in progress</span>
                )}
                {upload.status === 'completed' && (
                  <span className={processingOptions.enableIntelligentEditing ? "text-purple-600 font-medium" : "text-green-600"}>
                    {processingOptions.enableIntelligentEditing 
                      ? '🤖 AI processing will begin shortly...' 
                      : '📝 Caption processing will begin shortly...'
                    }
                  </span>
                )}
              </div>

              {/* Processing time estimate */}
              {upload.status === 'completed' && processingOptions.enableIntelligentEditing && (
                <div className="mt-2 p-2 bg-purple-50 rounded text-xs text-purple-700">
                  <div className="flex items-center">
                    <Clock className="w-3 h-3 mr-1" />
                    Estimated processing time: 2-5 minutes for intelligent editing
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
        </>
      )}
    </div>
  )
}