'use client'

import { useEffect, useState, useRef, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  data: any
}

interface UseWebSocketReturn {
  messages: WebSocketMessage[]
  sendMessage: (message: any) => void
  isConnected: boolean
}

export const useWebSocket = (url: string | null): UseWebSocketReturn => {
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!url) return

    console.log('Connecting to WebSocket:', url)
    const websocket = new WebSocket(url)

    websocket.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
    }

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('WebSocket message received:', data)
        setMessages((prev) => [...prev, data])
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    websocket.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
    }

    wsRef.current = websocket

    return () => {
      console.log('Closing WebSocket connection')
      websocket.close()
    }
  }, [url])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  return { messages, sendMessage, isConnected }
}
