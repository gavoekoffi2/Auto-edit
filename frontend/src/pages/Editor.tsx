import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Zap, Mic, VolumeX, Film, Sparkles, Loader2, ArrowLeft, Wand2, Type, Volume2, Palette } from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Timeline from '../components/video/Timeline'
import JobProgress from '../components/video/JobProgress'
import { getVideo, getStreamUrl } from '../api/videos'
import { createJob, listJobs } from '../api/jobs'
import { toast } from '../components/ui/Toast'

type EditMode = 'tiktok' | 'youtube' | 'podcast'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
}

const MODES = [
  { id: 'tiktok' as const, name: 'TikTok', icon: '🔥', desc: 'Vertical, fast, subtitled' },
  { id: 'youtube' as const, name: 'YouTube', icon: '🎥', desc: 'Optimized engagement' },
  { id: 'podcast' as const, name: 'Podcast', icon: '🎙️', desc: 'Audio cleanup' },
] as const

const SUBTITLE_PRESETS = [
  { id: 'karaoke', name: 'Karaoke', desc: 'TikTok viral style, word-by-word highlighting' },
  { id: 'classic', name: 'Classic', desc: 'Clean white text with outline' },
  { id: 'modern', name: 'Modern', desc: 'Semi-transparent background box' },
  { id: 'bold', name: 'Bold', desc: 'Large uppercase impact text' },
  { id: 'minimal', name: 'Minimal', desc: 'Small subtle text' },
  { id: 'neon', name: 'Neon', desc: 'Glowing colored text' },
] as const

const FONT_OPTIONS = ['Inter', 'Montserrat', 'Poppins', 'Oswald', 'Bebas Neue', 'Bangers'] as const

const INTENSITY_OPTIONS = [
  { id: 'subtle', label: 'Subtle' },
  { id: 'normal', label: 'Normal' },
  { id: 'intense', label: 'Intense' },
] as const

const POSITION_OPTIONS = [
  { id: 'bottom', label: 'Bottom' },
  { id: 'center', label: 'Center' },
  { id: 'top', label: 'Top' },
] as const

export default function Editor() {
  const { videoId } = useParams<{ videoId: string }>()
  const navigate = useNavigate()
  const [video, setVideo] = useState<Video | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [selectedMode, setSelectedMode] = useState<EditMode>('youtube')
  const [motionEnabled, setMotionEnabled] = useState(true)
  const [brandColor, setBrandColor] = useState('#6366f1')
  const [introTitle, setIntroTitle] = useState('')
  const [processing, setProcessing] = useState(false)
  const [completedResult, setCompletedResult] = useState<Record<string, unknown> | null>(null)
  const [loadError, setLoadError] = useState('')

  // New state variables
  const [captionStyle, setCaptionStyle] = useState('karaoke')
  const [fontFamily, setFontFamily] = useState('Inter')
  const [fontSize, setFontSize] = useState(36)
  const [subtitleColor, setSubtitleColor] = useState('#ffffff')
  const [subtitlePosition, setSubtitlePosition] = useState('bottom')
  const [subtitlePreset, setSubtitlePreset] = useState('karaoke')
  const [sfxEnabled, setSfxEnabled] = useState(true)
  const [sfxIntensity, setSfxIntensity] = useState('normal')
  const [animationIntensity, setAnimationIntensity] = useState('normal')

  useEffect(() => {
    if (!videoId) return
    let cancelled = false

    async function load() {
      try {
        const [videoData, jobs] = await Promise.all([
          getVideo(videoId!),
          listJobs(videoId!),
        ])
        if (cancelled) return
        setVideo(videoData)

        // Check for active or completed jobs
        const activeJob = jobs.find((j: { status: string }) => j.status === 'processing' || j.status === 'pending')
        if (activeJob) {
          setActiveJobId(activeJob.id)
          setProcessing(true)
        }
        const completed = jobs.find((j: { status: string }) => j.status === 'completed')
        if (completed?.result) {
          setCompletedResult(completed.result)
        }
      } catch {
        if (!cancelled) setLoadError('Failed to load video')
      }
    }

    load()
    return () => { cancelled = true }
  }, [videoId])

  const handleAutoEdit = useCallback(async () => {
    if (!videoId) return
    setProcessing(true)

    try {
      const params: Record<string, unknown> = {
        motion: motionEnabled
          ? {
              primary_color: brandColor,
              caption_style: captionStyle,
              font_family: fontFamily,
              animation_intensity: animationIntensity,
              ...(introTitle.trim()
                ? { intro: { title: introTitle.trim() } }
                : {}),
            }
          : { animated_captions: false, intro: false, outro: false },
        subtitle_style: {
          preset: subtitlePreset,
          font: fontFamily,
          fontSize: fontSize,
          color: subtitleColor,
          position: subtitlePosition,
        },
        sfx: {
          enabled: sfxEnabled,
          intensity: sfxIntensity,
        },
      }

      const job = await createJob({
        video_id: videoId,
        job_type: 'pipeline',
        mode: selectedMode,
        params,
      })
      setActiveJobId(job.id)
      toast('info', `Processing started in ${selectedMode} mode`)
    } catch (err: unknown) {
      setProcessing(false)
      let msg = 'Failed to start processing'
      if (err && typeof err === 'object' && 'response' in err) {
        msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
      }
      toast('error', msg)
    }
  }, [videoId, selectedMode, motionEnabled, brandColor, introTitle, captionStyle, fontFamily, fontSize, subtitleColor, subtitlePosition, subtitlePreset, sfxEnabled, sfxIntensity, animationIntensity])

  const handleJobComplete = useCallback((result: Record<string, unknown>) => {
    setCompletedResult(result)
    setProcessing(false)
    // Reload video data
    if (videoId) {
      getVideo(videoId).then(setVideo).catch(() => {})
    }
  }, [videoId])

  const handleRetry = useCallback(() => {
    setActiveJobId(null)
    setProcessing(false)
    handleAutoEdit()
  }, [handleAutoEdit])

  if (loadError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center">
        <p className="text-red-400 mb-4">{loadError}</p>
        <button onClick={() => navigate('/dashboard')} className="btn-secondary">
          Back to Dashboard
        </button>
      </div>
    )
  }

  if (!video) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    )
  }

  const scenes = completedResult?.scenes as { scenes: { start: number; end: number; duration: number }[] } | undefined

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-dark-400 hover:text-white transition-colors"
          aria-label="Back to dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{video.title}</h1>
          <p className="text-dark-400 text-sm">
            {video.status}
            {' · '}
            {(video.size_bytes / (1024 * 1024)).toFixed(1)} MB
            {video.duration_s != null && ` · ${Math.floor(video.duration_s / 60)}:${Math.floor(video.duration_s % 60).toString().padStart(2, '0')}`}
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Video Preview */}
        <div className="lg:col-span-2 space-y-4">
          <VideoPlayer src={getStreamUrl(videoId!)} />

          {/* Timeline */}
          {scenes?.scenes && scenes.scenes.length > 0 && (
            <Timeline
              scenes={scenes.scenes}
              totalDuration={video.duration_s || 0}
            />
          )}

          {/* Job Progress */}
          {activeJobId && processing && (
            <JobProgress
              jobId={activeJobId}
              onComplete={handleJobComplete}
              onRetry={handleRetry}
            />
          )}
        </div>

        {/* Controls Sidebar */}
        <div className="max-h-[calc(100vh-8rem)] overflow-y-auto space-y-4 pr-1">
          {/* Mode Selection */}
          <div className="card">
            <h3 className="font-semibold mb-3">Editing Mode</h3>
            <div className="space-y-2">
              {MODES.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all text-left
                    ${selectedMode === mode.id
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500'
                    }`}
                >
                  <span className="text-2xl">{mode.icon}</span>
                  <div>
                    <p className="font-medium">{mode.name}</p>
                    <p className="text-xs text-dark-400">{mode.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Motion Design */}
          {selectedMode !== 'podcast' && (
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-accent-400" />
                  Motion Design
                </h3>
                <button
                  type="button"
                  role="switch"
                  aria-checked={motionEnabled}
                  aria-label="Toggle motion design"
                  onClick={() => setMotionEnabled((v) => !v)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    motionEnabled ? 'bg-primary-600' : 'bg-dark-700'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                      motionEnabled ? 'translate-x-5' : ''
                    }`}
                  />
                </button>
              </div>
              <p className="text-xs text-dark-400 mb-3">
                Animated intro, word-by-word captions & end-screen (Remotion).
              </p>
              {motionEnabled && (
                <div className="space-y-3">
                  <label className="flex items-center justify-between text-sm">
                    <span className="text-dark-300">Brand color</span>
                    <input
                      type="color"
                      value={brandColor}
                      onChange={(e) => setBrandColor(e.target.value)}
                      aria-label="Brand color"
                      className="w-8 h-8 rounded bg-transparent border border-dark-600 cursor-pointer"
                    />
                  </label>
                  <input
                    type="text"
                    value={introTitle}
                    onChange={(e) => setIntroTitle(e.target.value)}
                    placeholder="Intro title (optional)"
                    maxLength={40}
                    className="w-full bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                  />

                  {/* Animation Intensity */}
                  <div>
                    <p className="text-sm text-dark-300 mb-2">Animation Intensity</p>
                    <div className="flex gap-2">
                      {INTENSITY_OPTIONS.map((opt) => (
                        <button
                          key={opt.id}
                          onClick={() => setAnimationIntensity(opt.id)}
                          className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                            animationIntensity === opt.id
                              ? 'border-primary-500 bg-primary-500/15 text-primary-400'
                              : 'border-dark-600 text-dark-400 hover:border-dark-500'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Subtitle Style */}
          <div className="card">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Type className="w-4 h-4 text-primary-400" />
              Subtitle Style
            </h3>

            {/* Preset Selector */}
            <div className="grid grid-cols-2 gap-2 mb-4">
              {SUBTITLE_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => {
                    setSubtitlePreset(preset.id)
                    setCaptionStyle(preset.id)
                  }}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    subtitlePreset === preset.id
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500'
                  }`}
                >
                  <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded mb-1 ${
                    subtitlePreset === preset.id ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-700 text-dark-400'
                  }`}>
                    {preset.name}
                  </span>
                  <p className="text-[10px] text-dark-400 leading-tight">{preset.desc}</p>
                </button>
              ))}
            </div>

            {/* Font Family */}
            <div className="mb-3">
              <label className="text-sm text-dark-300 mb-1.5 flex items-center gap-1.5">
                <Type className="w-3.5 h-3.5" />
                Font Family
              </label>
              <select
                value={fontFamily}
                onChange={(e) => setFontFamily(e.target.value)}
                className="w-full bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:border-primary-500 focus:outline-none appearance-none cursor-pointer"
              >
                {FONT_OPTIONS.map((font) => (
                  <option key={font} value={font}>{font}</option>
                ))}
              </select>
            </div>

            {/* Font Size */}
            <div className="mb-3">
              <label className="text-sm text-dark-300 mb-1.5 flex items-center justify-between">
                <span>Font Size</span>
                <span className="text-primary-400 font-mono text-xs">{fontSize}px</span>
              </label>
              <input
                type="range"
                min={24}
                max={56}
                value={fontSize}
                onChange={(e) => setFontSize(parseInt(e.target.value))}
                aria-label="Font size"
                className="w-full h-1.5 bg-dark-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-primary-500 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-dark-500 mt-1">
                <span>24px</span>
                <span>56px</span>
              </div>
            </div>

            {/* Subtitle Color */}
            <div className="mb-3">
              <label className="flex items-center justify-between text-sm">
                <span className="text-dark-300 flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5" />
                  Subtitle Color
                </span>
                <input
                  type="color"
                  value={subtitleColor}
                  onChange={(e) => setSubtitleColor(e.target.value)}
                  aria-label="Subtitle color"
                  className="w-8 h-8 rounded bg-transparent border border-dark-600 cursor-pointer"
                />
              </label>
            </div>

            {/* Subtitle Position */}
            <div>
              <p className="text-sm text-dark-300 mb-2">Position</p>
              <div className="flex gap-2">
                {POSITION_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setSubtitlePosition(opt.id)}
                    className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      subtitlePosition === opt.id
                        ? 'border-primary-500 bg-primary-500/15 text-primary-400'
                        : 'border-dark-600 text-dark-400 hover:border-dark-500'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Sound Effects */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-primary-400" />
                Sound Effects
              </h3>
              <button
                type="button"
                role="switch"
                aria-checked={sfxEnabled}
                aria-label="Toggle sound effects"
                onClick={() => setSfxEnabled((v) => !v)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  sfxEnabled ? 'bg-primary-600' : 'bg-dark-700'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                    sfxEnabled ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>
            <p className="text-xs text-dark-400 mb-3">
              Add automatic sound effects: whooshes, transitions, and emphasis sounds.
            </p>
            {sfxEnabled && (
              <div>
                <p className="text-sm text-dark-300 mb-2">Intensity</p>
                <div className="flex gap-2 mb-2">
                  {INTENSITY_OPTIONS.map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setSfxIntensity(opt.id)}
                      className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        sfxIntensity === opt.id
                          ? 'border-primary-500 bg-primary-500/15 text-primary-400'
                          : 'border-dark-600 text-dark-400 hover:border-dark-500'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-dark-500">
                  {sfxIntensity === 'subtle' && 'Light transition sounds only, barely noticeable.'}
                  {sfxIntensity === 'normal' && 'Balanced mix of whooshes, pops, and transition sounds.'}
                  {sfxIntensity === 'intense' && 'Full sound design with emphasis hits, bass drops, and dramatic transitions.'}
                </p>
              </div>
            )}
          </div>

          {/* Pipeline Steps */}
          <div className="card">
            <h3 className="font-semibold mb-3">Processing Steps</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-dark-300">
                <Mic className="w-4 h-4 text-primary-400" />
                AI Transcription (Whisper)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <VolumeX className="w-4 h-4 text-primary-400" />
                Silence Removal (auto-editor)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <Film className="w-4 h-4 text-primary-400" />
                Scene Detection (PySceneDetect)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <Sparkles className="w-4 h-4 text-primary-400" />
                Effects & Subtitles (MoviePy)
              </div>
              {sfxEnabled && (
                <div className="flex items-center gap-2 text-dark-300">
                  <Volume2 className="w-4 h-4 text-primary-400" />
                  Sound Effects ({sfxIntensity})
                </div>
              )}
              {selectedMode !== 'podcast' && motionEnabled && (
                <div className="flex items-center gap-2 text-dark-300">
                  <Wand2 className="w-4 h-4 text-accent-400" />
                  Motion Design (Remotion)
                </div>
              )}
            </div>
          </div>

          {/* AutoEdit Button */}
          <button
            onClick={handleAutoEdit}
            disabled={processing}
            className="btn-accent w-full py-4 text-lg flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {processing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                AutoEdit Now
              </>
            )}
          </button>

          {/* Transcription result */}
          {!!completedResult?.transcription && (
            <div className="card">
              <h3 className="font-semibold mb-2">Transcription</h3>
              <p className="text-sm text-dark-400 max-h-40 overflow-y-auto leading-relaxed">
                {(completedResult.transcription as { text: string }).text}
              </p>
            </div>
          )}

          {/* Steps summary */}
          {!!completedResult?.steps_completed && (
            <div className="card">
              <h3 className="font-semibold mb-2">Processing Summary</h3>
              <div className="text-sm space-y-1">
                {(completedResult.steps_completed as string[]).map((step) => (
                  <div key={step} className="flex items-center gap-2 text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {step.replace('_', ' ')}
                  </div>
                ))}
                {(completedResult.steps_failed as string[] | undefined)?.map((step) => (
                  <div key={step} className="flex items-center gap-2 text-red-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    {step.replace('_', ' ')} (failed)
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
