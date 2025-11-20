'use client'

import { useState } from 'react'
import { sendCommand } from '@/lib/api'

interface CommandInputProps {
  meetingId: string
}

export default function CommandInput({ meetingId }: CommandInputProps) {
  const [command, setCommand] = useState('')
  const [response, setResponse] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!command.trim()) return

    setIsLoading(true)
    setResponse(null)

    try {
      const result = await sendCommand({
        meeting_id: meetingId,
        command: command.trim(),
      })
      setResponse(result)
      setCommand('')
    } catch (error) {
      console.error('Error sending command:', error)
      setResponse({
        response: 'Fehler bei der Verarbeitung des Befehls',
        suggestions: [],
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center">
          <span className="mr-2">💬</span>
          Command / Frage an KI
        </h2>
      </div>

      <div className="p-6">
        <form onSubmit={handleSubmit} className="mb-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="z.B. Was sollte ich jetzt fragen?"
              disabled={isLoading}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 text-gray-900"
            />
            <button
              type="submit"
              disabled={isLoading || !command.trim()}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors duration-200"
            >
              {isLoading ? '...' : '▶'}
            </button>
          </div>
        </form>

        {/* Quick action buttons */}
        <div className="flex flex-wrap gap-2 mb-4">
          {[
            'Was sollte ich jetzt fragen?',
            'Welche Einwände wurden noch nicht behandelt?',
            'Zusammenfassung der Pain Points',
            'Welche Informationen fehlen?',
          ].map((quickCommand) => (
            <button
              key={quickCommand}
              onClick={() => setCommand(quickCommand)}
              disabled={isLoading}
              className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors duration-200"
            >
              {quickCommand}
            </button>
          ))}
        </div>

        {/* Response area */}
        {response && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm font-medium text-blue-800 mb-2">Antwort:</p>
            <p className="text-gray-800 mb-3">{response.response}</p>

            {response.suggestions && response.suggestions.length > 0 && (
              <div>
                <p className="text-sm font-medium text-blue-800 mb-2">Vorschläge:</p>
                <ul className="list-disc list-inside space-y-1">
                  {response.suggestions.map((suggestion: string, index: number) => (
                    <li key={index} className="text-sm text-gray-700">
                      {suggestion}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
