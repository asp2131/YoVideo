import { create } from 'zustand'

interface UploadState {
  uploading: boolean
  uploadProgress: number
  dragOver: boolean
  setUploading: (uploading: boolean) => void
  setUploadProgress: (progress: number) => void
  setDragOver: (dragOver: boolean) => void
  resetUpload: () => void
}

export const useUploadStore = create<UploadState>((set) => ({
  uploading: false,
  uploadProgress: 0,
  dragOver: false,
  setUploading: (uploading) => set({ uploading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  setDragOver: (dragOver) => set({ dragOver }),
  resetUpload: () => set({ uploading: false, uploadProgress: 0, dragOver: false }),
}))