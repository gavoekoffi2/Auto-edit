import { useRef, useState, useEffect } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, Loader2 } from 'lucide-react'

interface Props {
  src: string
}

export default function VideoPlayer({ src }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [loading, setLoading] = useState(true)
  const [blobUrl, setBlobUrl] = useState<string>('')
  const [error, setError] = useState('')

  // Fetch video with auth header instead of token in URL
  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    async function fetchVideo() {
      setLoading(true)
      setError('')
      try {
        const token = localStorage.getItem('access_token')
        const res = await fetch(src, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        })
        if (!res.ok) throw new Error(`Failed to load video (${res.status})`)
        const blob = await res.blob()
        if (!cancelled) {
          const url = URL.createObjectURL(blob)
          setBlobUrl(url)
        }
      } catch (err) {
        if (!cancelled && err instanceof Error && err.name !== 'AbortError') {
          setError(err.message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchVideo()
    return () => {
      cancelled = true
      controller.abort()
      // Revoke the blob URL on cleanup using the current state value
      setBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return ''
      })
    }
  }, [src])

  const togglePlay = () => {
    if (!videoRef.current) return
    if (playing) {
      videoRef.current.pause()
    } else {
      videoRef.current.play().catch(() => {
        // Autoplay may be blocked by browser policy
      })
    }
    setPlaying(!playing)
  }

  const toggleMute = () => {
    if (!videoRef.current) return
    videoRef.current.muted = !muted
    setMuted(!muted)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!videoRef.current) return
    const time = parseFloat(e.target.value)
    videoRef.current.currentTime = time
    setCurrentTime(time)
  }

  const toggleFullscreen = () => {
    if (!videoRef.current) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      videoRef.current.requestFullscreen()
    }
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  if (loading) {
    return (
      <div className="bg-black rounded-xl aspect-video flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-dark-900 rounded-xl aspect-video flex items-center justify-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    )
  }

  return (
    <div className="relative bg-black rounded-xl overflow-hidden group">
      <video
        ref={videoRef}
        src={blobUrl}
        className="w-full aspect-video"
        onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
        onLoadedMetadata={() => videoRef.current && setDuration(videoRef.current.duration)}
        onEnded={() => setPlaying(false)}
        onClick={togglePlay}
      />

      {/* Controls overlay */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <input
          type="range"
          min={0}
          max={duration || 0}
          value={currentTime}
          onChange={handleSeek}
          aria-label="Video progress"
          className="w-full h-1 bg-dark-600 rounded-full appearance-none cursor-pointer mb-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-primary-500 [&::-webkit-slider-thumb]:rounded-full"
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'} className="text-white hover:text-primary-400 transition-colors">
              {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </button>
            <button onClick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'} className="text-white hover:text-primary-400 transition-colors">
              {muted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </button>
            <span className="text-sm text-dark-300">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
          <button onClick={toggleFullscreen} aria-label="Fullscreen" className="text-white hover:text-primary-400 transition-colors">
            <Maximize className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
