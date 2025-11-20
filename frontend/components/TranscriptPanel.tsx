'use client'

import { useEffect, useRef } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { de } from 'date-fns/locale'

interface TranscriptSegment {
  timestamp: string
  speaker: string
  segment: string
  confidence: number
}

interface TranscriptPanelProps {
  transcripts: TranscriptSegment[]
}

export default function TranscriptPanel({ transcripts }: TranscriptPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new transcripts arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [transcripts])

  const getSpeakerColor = (speaker: string): string => {
    const colors: { [key: string]: string } = {
      speaker_0: 'bg-blue-100 text-blue-800',
      speaker_1: 'bg-green-100 text-green-800',
      speaker_2: 'bg-purple-100 text-purple-800',
      speaker_3: 'bg-orange-100 text-orange-800',
    }
    return colors[speaker] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center">
          <span className="mr-2">📝</span>
          Live Transkript
        </h2>
      </div>

      <div
        ref={scrollRef}
        className="h-96 overflow-y-auto p-6 space-y-4 scroll-smooth"
      >
        {transcripts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>Warten auf Transkripte...</p>
            <p className="text-sm mt-2">Das Meeting wird in Echtzeit transkribiert</p>
          </div>
        ) : (
          transcripts.map((transcript, index) => (
            <div key={index} className="flex gap-3">
              <div className="flex-shrink-0">
                <span
                  className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getSpeakerColor(
                    transcript.speaker
                  )}`}
                >
                  {transcript.speaker.replace('speaker_', 'Person ')}
                </span>
              </div>
              <div className="flex-1">
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(transcript.timestamp), {
                      addSuffix: true,
                      locale: de,
                    })}
                  </span>
                  {transcript.confidence && (
                    <span className="text-xs text-gray-400">
                      ({Math.round(transcript.confidence * 100)}%)
                    </span>
                  )}
                </div>
                <p className="text-gray-800">{transcript.segment}</p>
              </div>
            </div>
          ))
        )}
      </div>

      {transcripts.length > 0 && (
        <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            {transcripts.length} Segment{transcripts.length !== 1 ? 'e' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
