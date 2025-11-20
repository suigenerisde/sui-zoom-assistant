'use client'

interface Suggestion {
  type: string
  text: string
}

interface SuggestionsPanelProps {
  suggestions: Suggestion[]
}

export default function SuggestionsPanel({ suggestions }: SuggestionsPanelProps) {
  const getIcon = (type: string): string => {
    switch (type) {
      case 'question':
        return '❓'
      case 'pain_point':
        return '⚠️'
      case 'next_step':
        return '➡️'
      default:
        return '💡'
    }
  }

  const getTypeLabel = (type: string): string => {
    switch (type) {
      case 'question':
        return 'Offene Frage'
      case 'pain_point':
        return 'Pain Point'
      case 'next_step':
        return 'Nächster Schritt'
      default:
        return 'Vorschlag'
    }
  }

  const getTypeColor = (type: string): string => {
    switch (type) {
      case 'question':
        return 'bg-blue-50 border-blue-200'
      case 'pain_point':
        return 'bg-red-50 border-red-200'
      case 'next_step':
        return 'bg-green-50 border-green-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center">
          <span className="mr-2">🎯</span>
          KI-Vorschläge
        </h2>
      </div>

      <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
        {suggestions.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>Keine Vorschläge verfügbar</p>
            <p className="text-sm mt-2">KI-Vorschläge werden in Echtzeit generiert</p>
          </div>
        ) : (
          suggestions.map((suggestion, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border-2 ${getTypeColor(suggestion.type)}`}
            >
              <div className="flex items-start gap-3">
                <span className="text-2xl">{getIcon(suggestion.type)}</span>
                <div className="flex-1">
                  <p className="text-xs font-medium text-gray-600 mb-1">
                    {getTypeLabel(suggestion.type)}
                  </p>
                  <p className="text-sm text-gray-800">{suggestion.text}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            {suggestions.length} aktive{suggestions.length !== 1 ? '' : 'r'} Vorschlag
            {suggestions.length !== 1 ? 'e' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
