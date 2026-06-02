import { create } from 'zustand'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
  created_at: string
}

interface Job {
  id: string
  video_id: string
  job_type: string
  mode: string | null
  status: string
  progress: number
  result: Record<string, unknown> | null
  error_message: string | null
}

interface VideoState {
  videos: Video[]
  currentVideo: Video | null
  currentJob: Job | null
  uploadProgress: number
  setVideos: (videos: Video[]) => void
  setCurrentVideo: (video: Video | null) => void
  setCurrentJob: (job: Job | null) => void
  setUploadProgress: (progress: number) => void
}

export const useVideoStore = create<VideoState>((set) => ({
  videos: [],
  currentVideo: null,
  currentJob: null,
  uploadProgress: 0,

  setVideos: (videos) => set({ videos }),
  setCurrentVideo: (video) => set({ currentVideo: video }),
  setCurrentJob: (job) => set({ currentJob: job }),
  setUploadProgress: (progress) => set({ uploadProgress: progress }),
}))
