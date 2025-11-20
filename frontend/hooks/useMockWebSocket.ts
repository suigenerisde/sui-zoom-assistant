'use client'

import { useEffect, useState } from 'react'

interface WebSocketMessage {
  type: string
  data: any
}

interface UseMockWebSocketReturn {
  messages: WebSocketMessage[]
  sendMessage: (message: any) => void
  isConnected: boolean
}

// Mock transcript segments
const mockTranscripts = [
  {
    timestamp: new Date(Date.now() - 300000).toISOString(),
    speaker: 'speaker_0',
    segment: 'Guten Tag Herr Müller, vielen Dank dass Sie sich die Zeit nehmen.',
    confidence: 0.98,
  },
  {
    timestamp: new Date(Date.now() - 280000).toISOString(),
    speaker: 'speaker_1',
    segment: 'Sehr gerne, ich bin gespannt was Sie mir heute vorstellen.',
    confidence: 0.96,
  },
  {
    timestamp: new Date(Date.now() - 260000).toISOString(),
    speaker: 'speaker_0',
    segment: 'Ich würde gerne verstehen, welche Herausforderungen Sie aktuell im Vertrieb haben.',
    confidence: 0.97,
  },
  {
    timestamp: new Date(Date.now() - 240000).toISOString(),
    speaker: 'speaker_1',
    segment: 'Unser größtes Problem ist die fehlende Automatisierung. Wir verlieren viel Zeit mit manuellen Prozessen.',
    confidence: 0.95,
  },
  {
    timestamp: new Date(Date.now() - 220000).toISOString(),
    speaker: 'speaker_0',
    segment: 'Das kann ich gut nachvollziehen. Wie viel Zeit würden Sie schätzen geht dadurch verloren?',
    confidence: 0.94,
  },
  {
    timestamp: new Date(Date.now() - 200000).toISOString(),
    speaker: 'speaker_1',
    segment: 'Pro Woche verliert jeder Mitarbeiter mindestens 10 Stunden mit Dateneingabe und Follow-ups.',
    confidence: 0.96,
  },
  {
    timestamp: new Date(Date.now() - 180000).toISOString(),
    speaker: 'speaker_0',
    segment: 'Das sind bei 10 Mitarbeitern 100 Stunden pro Woche. Welche Lösungen haben Sie bisher in Betracht gezogen?',
    confidence: 0.97,
  },
  {
    timestamp: new Date(Date.now() - 160000).toISOString(),
    speaker: 'speaker_1',
    segment: 'Wir haben uns verschiedene CRM-Systeme angeschaut, aber die Implementierung war immer zu komplex.',
    confidence: 0.93,
  },
  {
    timestamp: new Date(Date.now() - 140000).toISOString(),
    speaker: 'speaker_0',
    segment: 'Verstehe. Wie sieht es mit dem Budget für eine Lösung aus?',
    confidence: 0.98,
  },
  {
    timestamp: new Date(Date.now() - 120000).toISOString(),
    speaker: 'speaker_1',
    segment: 'Wir haben ein Jahresbudget von etwa 50.000 Euro eingeplant, wenn die ROI-Rechnung aufgeht.',
    confidence: 0.95,
  },
]

// Mock AI suggestions
const mockSuggestions = {
  missing_questions: [
    'Wer ist außer Ihnen noch in den Entscheidungsprozess involviert?',
    'Wie sieht Ihr aktueller Prozess für Follow-ups konkret aus?',
    'Welche Integration mit bestehenden Systemen ist erforderlich?',
  ],
  pain_points: [
    'Zeitverlust durch manuelle Prozesse (100h/Woche)',
    'Komplexität bei CRM-Implementierungen',
    'Fehlende Automatisierung im Vertrieb',
  ],
  next_steps: [
    'Entscheidungsprozess und Stakeholder klären',
    'Timeline für Implementierung besprechen',
    'ROI-Berechnung mit konkreten Zahlen präsentieren',
  ],
}

export const useMockWebSocket = (url: string | null): UseMockWebSocketReturn => {
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    if (!url) return

    // Simulate connection
    setIsConnected(true)

    // Send initial transcripts
    const initialMessages = mockTranscripts.slice(0, 5).map((transcript) => ({
      type: 'transcript_update',
      data: transcript,
    }))
    setMessages(initialMessages)
    setCurrentIndex(5)

    // Send suggestions after a short delay
    const suggestionsTimeout = setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          type: 'suggestion_update',
          data: mockSuggestions,
        },
      ])
    }, 2000)

    // Gradually add more transcripts
    const interval = setInterval(() => {
      setCurrentIndex((prevIndex) => {
        if (prevIndex >= mockTranscripts.length) {
          clearInterval(interval)
          return prevIndex
        }

        setMessages((prev) => [
          ...prev,
          {
            type: 'transcript_update',
            data: mockTranscripts[prevIndex],
          },
        ])

        // Update suggestions every few segments
        if (prevIndex % 3 === 0) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'suggestion_update',
              data: mockSuggestions,
            },
          ])
        }

        return prevIndex + 1
      })
    }, 5000) // Add new transcript every 5 seconds

    // Simulate stats updates
    const statsInterval = setInterval(() => {
      setMessages((prev) => [
        ...prev,
        {
          type: 'meeting_stats',
          data: {
            duration_minutes: Math.floor((Date.now() % 3600000) / 60000),
            segment_count: currentIndex,
            speaker_stats: {
              speaker_0: Math.floor(currentIndex * 0.45),
              speaker_1: Math.floor(currentIndex * 0.55),
            },
          },
        },
      ])
    }, 10000)

    return () => {
      clearTimeout(suggestionsTimeout)
      clearInterval(interval)
      clearInterval(statsInterval)
      setIsConnected(false)
    }
  }, [url])

  const sendMessage = (message: any) => {
    console.log('Mock WebSocket: sending message', message)
    // In demo mode, simulate command response
    if (message.type === 'command') {
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            type: 'command_response',
            data: {
              command: message.data,
              response: {
                response:
                  'Basierend auf dem bisherigen Gespräch fehlen noch wichtige Informationen zum Entscheidungsprozess und zur Timeline. Der Kunde hat Budget und Pain Points klar kommuniziert.',
                suggestions: [
                  'Fragen Sie nach weiteren Stakeholdern im Entscheidungsprozess',
                  'Klären Sie die gewünschte Timeline für die Implementierung',
                  'Präsentieren Sie eine konkrete ROI-Rechnung basierend auf den 100h Zeitersparnis',
                ],
              },
            },
          },
        ])
      }, 1000)
    }
  }

  return { messages, sendMessage, isConnected }
}
