'use client'

import { useState, useEffect } from 'react'
import MeetingDashboard from '../components/MeetingDashboard'
import BotDashboard from '../components/BotDashboard'
import StartMeetingForm from '../components/StartMeetingForm'
import { getBotStatus } from '../lib/api'

export default function Home() {
  const [meetingId, setMeetingId] = useState<string | null>(null)
  const [hasBotSession, setHasBotSession] = useState(false)
  const [isChecking, setIsChecking] = useState(true)

  // Check if there's an active bot session on load
  useEffect(() => {
    const checkBotSession = async () => {
      try {
        const status = await getBotStatus()
        if (status.has_active_session) {
          setHasBotSession(true)
        }
      } catch (err) {
        console.log('No active bot session')
      } finally {
        setIsChecking(false)
      }
    }
    checkBotSession()
  }, [])

  const handleMeetingStarted = (id: string) => {
    setMeetingId(id)
  }

  const handleMeetingStopped = () => {
    setMeetingId(null)
    setHasBotSession(false)
  }

  // Show loading while checking
  if (isChecking) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Lade...</div>
      </main>
    )
  }

  // Show bot dashboard if there's an active bot session
  if (hasBotSession) {
    return <BotDashboard onStopped={handleMeetingStopped} />
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {!meetingId ? (
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-2xl mx-auto">
            <h1 className="text-4xl font-bold text-center mb-2 text-gray-900">
              Zoom Meeting AI Assistant
            </h1>
            <p className="text-center text-gray-600 mb-8">
              KI-gestützter Assistent für Verkaufsgespräche und Meetings
            </p>

            {/* Active Bot Session Check */}
            <div className="mb-6 p-4 bg-green-50 border-2 border-green-200 rounded-lg">
              <p className="text-center text-green-800 mb-3">
                <strong>Bot-Modus aktiv!</strong> Falls bereits eine Transkription läuft:
              </p>
              <button
                onClick={() => setHasBotSession(true)}
                className="block w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 text-center"
              >
                Zum Live-Dashboard
              </button>
            </div>

            <div className="mb-6 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
              <p className="text-center text-blue-800 mb-3">
                <strong>Demo-Modus verfügbar!</strong> Schau dir das Dashboard mit Beispiel-Daten an:
              </p>
              <a
                href="/demo"
                className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 text-center"
              >
                Demo ansehen
              </a>
            </div>

            <StartMeetingForm onMeetingStarted={handleMeetingStarted} />
          </div>
        </div>
      ) : (
        <MeetingDashboard
          meetingId={meetingId}
          onMeetingStopped={handleMeetingStopped}
        />
      )}
    </main>
  )
}
