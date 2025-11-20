'use client'

import { useState } from 'react'
import { startMeeting } from '@/lib/api'

interface StartMeetingFormProps {
  onMeetingStarted: (meetingId: string) => void
}

export default function StartMeetingForm({ onMeetingStarted }: StartMeetingFormProps) {
  const [meetingUrl, setMeetingUrl] = useState('')
  const [meetingName, setMeetingName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const response = await startMeeting({
        meeting_url: meetingUrl,
        meeting_name: meetingName || 'Untitled Meeting',
      })

      onMeetingStarted(response.meeting_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Fehler beim Starten des Meetings')
      console.error('Error starting meeting:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Neues Meeting starten</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="meetingName" className="block text-sm font-medium text-gray-700 mb-1">
            Meeting-Name
          </label>
          <input
            type="text"
            id="meetingName"
            value={meetingName}
            onChange={(e) => setMeetingName(e.target.value)}
            placeholder="z.B. Verkaufsgespräch mit Max Mustermann"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
          />
        </div>

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

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading || !meetingUrl}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200"
        >
          {isLoading ? 'Wird gestartet...' : 'Meeting beitreten'}
        </button>
      </form>

      <div className="mt-6 p-4 bg-blue-50 rounded-lg">
        <p className="text-sm text-blue-800">
          <strong>Hinweis:</strong> Der Bot wird dem Meeting als Teilnehmer beitreten und das Gespräch in
          Echtzeit transkribieren. Stelle sicher, dass alle Teilnehmer über die Aufzeichnung informiert
          sind.
        </p>
      </div>
    </div>
  )
}
