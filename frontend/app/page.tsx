'use client'

import { useState } from 'react'
import MeetingDashboard from '@/components/MeetingDashboard'
import StartMeetingForm from '@/components/StartMeetingForm'

export default function Home() {
  const [meetingId, setMeetingId] = useState<string | null>(null)

  const handleMeetingStarted = (id: string) => {
    setMeetingId(id)
  }

  const handleMeetingStopped = () => {
    setMeetingId(null)
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
