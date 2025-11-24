import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface StartMeetingRequest {
  meeting_url: string
  meeting_name?: string
}

export interface StartLocalTranscriptionRequest {
  meeting_name?: string
  device_index?: number
  language?: string
}

export interface MeetingResponse {
  meeting_id: string
  status: string
  message?: string
}

export interface CommandRequest {
  meeting_id: string
  command: string
}

export const startMeeting = async (data: StartMeetingRequest): Promise<MeetingResponse> => {
  const response = await api.post('/api/meeting/start', data)
  return response.data
}

export const startLocalTranscription = async (data: StartLocalTranscriptionRequest = {}): Promise<MeetingResponse> => {
  const response = await api.post('/api/meeting/start-local', data)
  return response.data
}

export const stopMeeting = async (meetingId: string): Promise<MeetingResponse> => {
  const response = await api.post('/api/meeting/stop', { meeting_id: meetingId })
  return response.data
}

export const getMeetingStatus = async (meetingId: string) => {
  const response = await api.get(`/api/meeting/${meetingId}/status`)
  return response.data
}

export const sendCommand = async (data: CommandRequest) => {
  const response = await api.post('/api/command', data)
  return response.data
}

export const getWebSocketUrl = (meetingId: string): string => {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
  return `${wsUrl}/ws/${meetingId}`
}

// Zoom Bot API (new flow)
export interface JoinBotRequest {
  join_url: string
  display_name?: string
}

export const joinBot = async (data: JoinBotRequest) => {
  const response = await api.post('/api/bot/join', data)
  return response.data
}

export const leaveBot = async () => {
  const response = await api.post('/api/bot/leave')
  return response.data
}

export const getBotStatus = async () => {
  const response = await api.get('/api/bot/status')
  return response.data
}

export const getBotTranscript = async () => {
  const response = await api.get('/api/bot/transcript')
  return response.data
}
