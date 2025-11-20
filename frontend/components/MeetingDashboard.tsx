'use client'

import { useEffect, useState } from 'react'
import { stopMeeting, getMeetingStatus, getWebSocketUrl } from '@/lib/api'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useMockWebSocket } from '@/hooks/useMockWebSocket'
import TranscriptPanel from './TranscriptPanel'
import SuggestionsPanel from './SuggestionsPanel'
import CommandInput from './CommandInput'
import MeetingHeader from './MeetingHeader'
import MeetingStats from './MeetingStats'

interface MeetingDashboardProps {
  meetingId: string
  onMeetingStopped: () => void
}

interface TranscriptSegment {
  timestamp: string
  speaker: string
  segment: string
  confidence: number
}

interface Suggestion {
  type: string
  text: string
}

export default function MeetingDashboard({ meetingId, onMeetingStopped }: MeetingDashboardProps) {
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [meetingStatus, setMeetingStatus] = useState<any>(null)
  const [isStopping, setIsStopping] = useState(false)

  // Use mock data for demo mode
  const isDemoMode = meetingId.includes('demo')
  const wsUrl = isDemoMode ? 'ws://demo' : getWebSocketUrl(meetingId)
  const { messages, isConnected } = isDemoMode
    ? useMockWebSocket(wsUrl)
    : useWebSocket(wsUrl)

  // Fetch initial meeting status
  useEffect(() => {
    if (isDemoMode) {
      // Set mock meeting status for demo
      setMeetingStatus({
        meeting_id: meetingId,
        meeting_name: 'Demo: Verkaufsgespräch Max Mustermann',
        duration_minutes: 15.5,
        segment_count: 10,
        speaker_stats: {
          speaker_0: 5,
          speaker_1: 5,
        },
      })
      return
    }

    const fetchStatus = async () => {
      try {
        const status = await getMeetingStatus(meetingId)
        setMeetingStatus(status)
      } catch (error) {
        console.error('Error fetching meeting status:', error)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Update every 5 seconds

    return () => clearInterval(interval)
  }, [meetingId, isDemoMode])

  // Process WebSocket messages
  useEffect(() => {
    messages.forEach((message) => {
      switch (message.type) {
        case 'transcript_update':
          setTranscripts((prev) => [...prev, message.data])
          break
        case 'suggestion_update':
          // Parse suggestions from n8n
          const newSuggestions: Suggestion[] = []
          if (message.data.missing_questions) {
            message.data.missing_questions.forEach((q: string) => {
              newSuggestions.push({ type: 'question', text: q })
            })
          }
          if (message.data.pain_points) {
            message.data.pain_points.forEach((p: string) => {
              newSuggestions.push({ type: 'pain_point', text: p })
            })
          }
          if (message.data.next_steps) {
            message.data.next_steps.forEach((s: string) => {
              newSuggestions.push({ type: 'next_step', text: s })
            })
          }
          setSuggestions(newSuggestions)
          break
        case 'command_response':
          // Handle command responses
          console.log('Command response:', message.data)
          break
        case 'meeting_stats':
          setMeetingStatus(message.data)
          break
      }
    })
  }, [messages])

  const handleStopMeeting = async () => {
    if (!confirm('Möchten Sie das Meeting wirklich beenden?')) return

    setIsStopping(true)
    try {
      await stopMeeting(meetingId)
      onMeetingStopped()
    } catch (error) {
      console.error('Error stopping meeting:', error)
      alert('Fehler beim Beenden des Meetings')
    } finally {
      setIsStopping(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <MeetingHeader
        meetingName={meetingStatus?.meeting_name || 'Meeting'}
        duration={meetingStatus?.duration_minutes || 0}
        isConnected={isConnected}
        onStop={handleStopMeeting}
        isStopping={isStopping}
      />

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main content area - Transcript and Command */}
          <div className="lg:col-span-2 space-y-6">
            <TranscriptPanel transcripts={transcripts} />
            <CommandInput meetingId={meetingId} />
          </div>

          {/* Sidebar - Suggestions and Stats */}
          <div className="lg:col-span-1 space-y-6">
            <SuggestionsPanel suggestions={suggestions} />
            <MeetingStats
              duration={meetingStatus?.duration_minutes || 0}
              segmentCount={meetingStatus?.segment_count || 0}
              speakerStats={meetingStatus?.speaker_stats || {}}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
