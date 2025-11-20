'use client'

interface MeetingStatsProps {
  duration: number
  segmentCount: number
  speakerStats: { [key: string]: number }
}

export default function MeetingStats({
  duration,
  segmentCount,
  speakerStats,
}: MeetingStatsProps) {
  const totalSegments = Object.values(speakerStats).reduce((sum, count) => sum + count, 0)

  const getSpeakerPercentage = (speaker: string): number => {
    if (totalSegments === 0) return 0
    return Math.round((speakerStats[speaker] / totalSegments) * 100)
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center">
          <span className="mr-2">📊</span>
          Meeting-Statistiken
        </h2>
      </div>

      <div className="p-6 space-y-4">
        <div>
          <p className="text-sm text-gray-600 mb-1">Dauer</p>
          <p className="text-2xl font-semibold text-gray-800">
            {Math.floor(duration)} min
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-600 mb-1">Segmente</p>
          <p className="text-2xl font-semibold text-gray-800">{segmentCount}</p>
        </div>

        {Object.keys(speakerStats).length > 0 && (
          <div>
            <p className="text-sm text-gray-600 mb-2">Redezeit-Verteilung</p>
            <div className="space-y-2">
              {Object.entries(speakerStats).map(([speaker, count]) => (
                <div key={speaker}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700">
                      {speaker.replace('speaker_', 'Person ')}
                    </span>
                    <span className="font-medium text-gray-900">
                      {getSpeakerPercentage(speaker)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getSpeakerPercentage(speaker)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
