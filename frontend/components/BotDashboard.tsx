'use client'

import { useEffect, useState } from 'react'
import { getBotStatus, getBotTranscript, leaveBot } from '../lib/api'

interface BotDashboardProps {
  onStopped: () => void
}

interface TranscriptSegment {
  transcript: string
  is_final: boolean
  confidence: number
  segment_number: number
}

export default function BotDashboard({ onStopped }: BotDashboardProps) {
  const [status, setStatus] = useState<any>(null)
  const [transcript, setTranscript] = useState<string>('')
  const [segments, setSegments] = useState<TranscriptSegment[]>([])
  const [isStopping, setIsStopping] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Poll for status and transcript
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusRes, transcriptRes] = await Promise.all([
          getBotStatus(),
          getBotTranscript()
        ])
        setStatus(statusRes)
        setTranscript(transcriptRes.transcript || '')
        setSegments(transcriptRes.segments || [])
        setError(null)
      } catch (err: any) {
        console.error('Error fetching data:', err)
        setError(err.message || 'Verbindungsfehler')
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [])

  const handleStop = async () => {
    if (!confirm('Möchten Sie die Transkription beenden?')) return

    setIsStopping(true)
    try {
      await leaveBot()
      onStopped()
    } catch (err: any) {
      console.error('Error stopping:', err)
      alert('Fehler beim Beenden: ' + (err.message || 'Unbekannter Fehler'))
    } finally {
      setIsStopping(false)
    }
  }

  const session = status?.session
  const audioStatus = status?.audio_service_status
  const deepgramStatus = audioStatus?.deepgram_status

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Zoom Bot Transkription
            </h1>
            <p className="text-sm text-gray-500">
              Meeting: {session?.meeting_id || 'Nicht verbunden'}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${
                audioStatus?.bot_connected && audioStatus?.deepgram_connected
                  ? 'bg-green-500'
                  : 'bg-yellow-500'
              }`} />
              <span className="text-sm text-gray-600">
                {audioStatus?.bot_connected && audioStatus?.deepgram_connected
                  ? 'Verbunden'
                  : 'Verbindung wird hergestellt...'}
              </span>
            </div>
            <button
              onClick={handleStop}
              disabled={isStopping}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:bg-gray-400"
            >
              {isStopping ? 'Wird beendet...' : 'Beenden'}
            </button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Transcript Panel */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">
                Live Transkript
              </h2>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              <div className="bg-gray-50 rounded-lg p-4 min-h-[400px] max-h-[600px] overflow-y-auto">
                {transcript ? (
                  <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {transcript}
                  </p>
                ) : (
                  <p className="text-gray-400 italic">
                    Warte auf Transkription... Sprechen Sie ins Meeting.
                  </p>
                )}
              </div>

              {/* Stats */}
              <div className="mt-4 flex gap-4 text-sm text-gray-500">
                <span>Segmente: {deepgramStatus?.segments_received || 0}</span>
                <span>•</span>
                <span>Modell: {deepgramStatus?.model || 'nova-2'}</span>
                <span>•</span>
                <span>Sprache: {deepgramStatus?.language || 'de'}</span>
              </div>
            </div>
          </div>

          {/* Sidebar - Status */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">
                Status
              </h2>

              <div className="space-y-4">
                {/* Bot Status */}
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Zoom Bot</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    audioStatus?.bot_connected
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {audioStatus?.bot_connected ? 'Verbunden' : 'Wartend'}
                  </span>
                </div>

                {/* Deepgram Status */}
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Deepgram</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    audioStatus?.deepgram_connected
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {audioStatus?.deepgram_connected ? 'Verbunden' : 'Wartend'}
                  </span>
                </div>

                {/* Session Status */}
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Session</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    session?.status === 'transcribing'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {session?.status || 'Inaktiv'}
                  </span>
                </div>

                {/* Divider */}
                <hr className="my-4" />

                {/* Meeting Info */}
                {session && (
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-gray-500">Meeting ID:</span>
                      <span className="ml-2 text-gray-800">{session.meeting_id}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Gestartet:</span>
                      <span className="ml-2 text-gray-800">
                        {new Date(session.started_at).toLocaleTimeString('de-DE')}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Recent Segments */}
            <div className="bg-white rounded-lg shadow-md p-6 mt-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">
                Letzte Segmente
              </h2>
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {segments.slice(-10).reverse().map((seg, idx) => (
                  <div key={idx} className="text-sm p-2 bg-gray-50 rounded">
                    <span className="text-gray-400">#{seg.segment_number}</span>
                    <span className="ml-2 text-gray-700">{seg.transcript}</span>
                    {seg.is_final && (
                      <span className="ml-2 text-green-600 text-xs">✓</span>
                    )}
                  </div>
                ))}
                {segments.length === 0 && (
                  <p className="text-gray-400 text-sm italic">Noch keine Segmente</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
