'use client'

import { useState, useEffect } from 'react'
import MeetingDashboard from '@/components/MeetingDashboard'

export default function DemoPage() {
  // Simulate meeting already started
  const demoMeetingId = 'demo-meeting-123'

  return (
    <main className="min-h-screen bg-gray-50">
      <MeetingDashboard
        meetingId={demoMeetingId}
        onMeetingStopped={() => {
          window.location.href = '/'
        }}
      />
    </main>
  )
}
