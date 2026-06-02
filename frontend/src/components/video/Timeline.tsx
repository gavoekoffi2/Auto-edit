interface Scene {
  start: number
  end: number
  duration: number
}

interface Props {
  scenes: Scene[]
  totalDuration: number
  currentTime?: number
  onSeek?: (time: number) => void
}

const SCENE_COLORS = [
  'bg-primary-500', 'bg-accent-500', 'bg-emerald-500', 'bg-purple-500',
  'bg-rose-500', 'bg-cyan-500', 'bg-amber-500', 'bg-indigo-500',
]

export default function Timeline({ scenes, totalDuration, currentTime = 0, onSeek }: Props) {
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!onSeek || !totalDuration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percent = x / rect.width
    onSeek(percent * totalDuration)
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-dark-400 mb-3">
        Timeline ({scenes.length} scenes)
      </h3>

      <div
        className="relative h-12 bg-dark-800 rounded-lg overflow-hidden cursor-pointer"
        onClick={handleClick}
      >
        {scenes.map((scene, i) => {
          const left = (scene.start / totalDuration) * 100
          const width = (scene.duration / totalDuration) * 100
          const color = SCENE_COLORS[i % SCENE_COLORS.length]

          return (
            <div
              key={i}
              className={`absolute top-0 h-full ${color} opacity-70 hover:opacity-100 transition-opacity border-r border-dark-900`}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`Scene ${i + 1}: ${scene.start.toFixed(1)}s - ${scene.end.toFixed(1)}s`}
            >
              <span className="text-[10px] text-white font-medium px-1 truncate block mt-1">
                {i + 1}
              </span>
            </div>
          )
        })}

        {/* Playhead */}
        {totalDuration > 0 && (
          <div
            className="absolute top-0 h-full w-0.5 bg-white shadow-lg z-10"
            style={{ left: `${(currentTime / totalDuration) * 100}%` }}
          />
        )}
      </div>

      {/* Time markers */}
      <div className="flex justify-between mt-1 text-xs text-dark-500">
        <span>0:00</span>
        <span>{formatTime(totalDuration / 4)}</span>
        <span>{formatTime(totalDuration / 2)}</span>
        <span>{formatTime((totalDuration * 3) / 4)}</span>
        <span>{formatTime(totalDuration)}</span>
      </div>
    </div>
  )
}

function formatTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}
