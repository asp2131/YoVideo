// hooks/use-chunked-upload.ts
import { useState, useCallback } from 'react'

interface ChunkedUploadOptions {
  chunkSize?: number
  maxRetries?: number
  onProgress?: (progress: number) => void
  onChunkProgress?: (chunkIndex: number, totalChunks: number) => void
}

interface ChunkMetadata {
  chunkIndex: number
  chunkSize: number
  totalChunks: number
  totalSize: number
  fileName: string
  fileType: string
}

export const useChunkedUpload = () => {
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const uploadFile = useCallback(async (
    file: File,
    projectName: string,
    options: ChunkedUploadOptions = {}
  ) => {
    const {
      chunkSize = 5 * 1024 * 1024, // 5MB chunks
      maxRetries = 3,
      onProgress,
      onChunkProgress
    } = options

    setIsUploading(true)
    setError(null)
    setProgress(0)

    try {
      const totalChunks = Math.ceil(file.size / chunkSize)
      const uploadId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      
      // Initialize multipart upload
      const initResponse = await fetch('/api/v1/upload/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type,
          projectName,
          totalChunks,
          uploadId
        })
      })

      if (!initResponse.ok) {
        throw new Error('Failed to initialize upload')
      }

      const { projectId } = await initResponse.json()
      const uploadedChunks: string[] = []

      // Upload chunks
      for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
        const start = chunkIndex * chunkSize
        const end = Math.min(start + chunkSize, file.size)
        const chunk = file.slice(start, end)

        let retries = 0
        let chunkUploaded = false

        while (retries < maxRetries && !chunkUploaded) {
          try {
            const formData = new FormData()
            formData.append('chunk', chunk)
            formData.append('metadata', JSON.stringify({
              chunkIndex,
              chunkSize: chunk.size,
              totalChunks,
              totalSize: file.size,
              fileName: file.name,
              fileType: file.type,
              uploadId,
              projectId
            } as ChunkMetadata))

            const chunkResponse = await fetch('/api/v1/upload/chunk', {
              method: 'POST',
              body: formData
            })

            if (!chunkResponse.ok) {
              throw new Error(`Chunk ${chunkIndex} upload failed`)
            }

            const { etag } = await chunkResponse.json()
            uploadedChunks[chunkIndex] = etag
            chunkUploaded = true

            // Update progress
            const progressPercent = ((chunkIndex + 1) / totalChunks) * 100
            setProgress(progressPercent)
            onProgress?.(progressPercent)
            onChunkProgress?.(chunkIndex + 1, totalChunks)

          } catch (chunkError) {
            retries++
            if (retries >= maxRetries) {
              throw new Error(`Failed to upload chunk ${chunkIndex} after ${maxRetries} retries`)
            }
            // Wait before retry with exponential backoff
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, retries) * 1000))
          }
        }
      }

      // Complete multipart upload
      const completeResponse = await fetch('/api/v1/upload/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uploadId,
          projectId,
          chunks: uploadedChunks
        })
      })

      if (!completeResponse.ok) {
        throw new Error('Failed to complete upload')
      }

      const result = await completeResponse.json()
      
      // Start transcription
      await fetch('/api/v1/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId })
      })

      return result

    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed')
      throw uploadError
    } finally {
      setIsUploading(false)
    }
  }, [])

  return {
    uploadFile,
    isUploading,
    progress,
    error,
    reset: () => {
      setProgress(0)
      setError(null)
      setIsUploading(false)
    }
  }
}