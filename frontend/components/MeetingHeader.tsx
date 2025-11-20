'use client'

interface MeetingHeaderProps {
  meetingName: string
  duration: number
  isConnected: boolean
  onStop: () => void
  isStopping: boolean
}

export default function MeetingHeader({
  meetingName,
  duration,
  isConnected,
  onStop,
  isStopping,
}: MeetingHeaderProps) {
  const formatDuration = (minutes: number): string => {
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    const secs = Math.floor((minutes * 60) % 60)

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="bg-white border-b border-gray-200 shadow-sm">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-2xl">🎥</span>
            <div>
              <h1 className="text-xl font-semibold text-gray-800">{meetingName}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-sm text-gray-600">⏱ {formatDuration(duration)}</span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                    isConnected
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isConnected ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  ></span>
                  {isConnected ? 'Verbunden' : 'Getrennt'}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={onStop}
            disabled={isStopping}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors duration-200"
          >
            {isStopping ? 'Wird beendet...' : 'Meeting beenden'}
          </button>
        </div>
      </div>
    </div>
  )
}
