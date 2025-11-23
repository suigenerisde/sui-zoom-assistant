'use client'

import { useState } from 'react'
import { startMeeting, startLocalTranscription } from '@/lib/api'

interface StartMeetingFormProps {
  onMeetingStarted: (meetingId: string) => void
}

export default function StartMeetingForm({ onMeetingStarted }: StartMeetingFormProps) {
  const [meetingUrl, setMeetingUrl] = useState('')
  const [meetingName, setMeetingName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'zoom' | 'local'>('local')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      let response
      if (mode === 'local') {
        response = await startLocalTranscription({
          meeting_name: meetingName || 'Local Transcription',
          language: 'de'
        })
      } else {
        response = await startMeeting({
          meeting_url: meetingUrl,
          meeting_name: meetingName || 'Untitled Meeting',
        })
      }

      onMeetingStarted(response.meeting_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Fehler beim Starten')
      console.error('Error starting:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Transkription starten</h2>

      {/* Mode Toggle */}
      <div className="mb-6">
        <div className="flex rounded-lg bg-gray-100 p-1">
          <button
            type="button"
            onClick={() => setMode('local')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              mode === 'local'
                ? 'bg-green-600 text-white shadow'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            Lokale Transkription
          </button>
          <button
            type="button"
            onClick={() => setMode('zoom')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              mode === 'zoom'
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            Zoom Meeting
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="meetingName" className="block text-sm font-medium text-gray-700 mb-1">
            {mode === 'local' ? 'Session-Name' : 'Meeting-Name'}
          </label>
          <input
            type="text"
            id="meetingName"
            value={meetingName}
            onChange={(e) => setMeetingName(e.target.value)}
            placeholder={mode === 'local' ? 'z.B. YouTube Video Test' : 'z.B. Verkaufsgespräch mit Max Mustermann'}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
          />
        </div>

        {mode === 'zoom' && (
          <div>
            <label htmlFor="meetingUrl" className="block text-sm font-medium text-gray-700 mb-1">
              Zoom Meeting URL *
            </label>
            <input
              type="text"
              id="meetingUrl"
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              placeholder="https://zoom.us/j/..."
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
            />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading || (mode === 'zoom' && !meetingUrl)}
          className={`w-full font-semibold py-3 px-6 rounded-lg transition-colors duration-200 text-white ${
            mode === 'local'
              ? 'bg-green-600 hover:bg-green-700 disabled:bg-gray-400'
              : 'bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400'
          }`}
        >
          {isLoading ? 'Wird gestartet...' : (mode === 'local' ? 'Lokale Transkription starten' : 'Meeting beitreten')}
        </button>
      </form>

      <div className={`mt-6 p-4 rounded-lg ${mode === 'local' ? 'bg-green-50' : 'bg-blue-50'}`}>
        {mode === 'local' ? (
          <p className="text-sm text-green-800">
            <strong>Lokale Transkription:</strong> Transkribiert Audio von BlackHole (System-Audio).
            Perfekt zum Testen mit YouTube-Videos oder anderen Audio-Quellen. Stelle sicher, dass
            BlackHole als Audio-Eingang konfiguriert ist.
          </p>
        ) : (
          <p className="text-sm text-blue-800">
            <strong>Hinweis:</strong> Der Bot wird dem Meeting als Teilnehmer beitreten und das Gespräch in
            Echtzeit transkribieren. Stelle sicher, dass alle Teilnehmer über die Aufzeichnung informiert
            sind.
          </p>
        )}
      </div>
    </div>
  )
}
