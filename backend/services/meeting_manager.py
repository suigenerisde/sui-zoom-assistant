"""
Meeting Manager - Orchestrates all meeting-related services
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
import uuid
from fastapi import WebSocket

from config.settings import settings
from services.zoom_bot import ZoomBot
from services.transcription_service import TranscriptionService
from services.webhook_manager import WebhookManager

logger = logging.getLogger(__name__)


class MeetingSession:
    """Represents an active meeting session"""

    def __init__(self, meeting_id: str, meeting_name: str, meeting_url: str):
        self.meeting_id = meeting_id
        self.meeting_name = meeting_name
        self.meeting_url = meeting_url
        self.start_time = datetime.utcnow()

        # Services
        self.zoom_bot: Optional[ZoomBot] = None
        self.transcription: Optional[TranscriptionService] = None

        # WebSocket connections
        self.websockets: list[WebSocket] = []

        # Stats
        self.segment_count = 0
        self.speaker_stats: Dict[str, int] = {}

    def get_duration_minutes(self) -> float:
        """Get meeting duration in minutes"""
        delta = datetime.utcnow() - self.start_time
        return delta.total_seconds() / 60


class MeetingManager:
    """
    Central manager for all meeting operations

    Coordinates:
    - Zoom bot lifecycle
    - Transcription service
    - Webhook communications
    - WebSocket connections to frontend
    """

    def __init__(self):
        self.sessions: Dict[str, MeetingSession] = {}
        self.webhook_manager: Optional[WebhookManager] = None

        logger.info("MeetingManager initialized")

    async def initialize(self):
        """Initialize manager and dependencies"""
        # Initialize webhook manager
        self.webhook_manager = WebhookManager(
            transcript_webhook_url=settings.n8n_transcript_webhook,
            command_webhook_url=settings.n8n_command_webhook
        )
        await self.webhook_manager.initialize()

        logger.info("MeetingManager ready")

    async def cleanup(self):
        """Cleanup all active sessions and connections"""
        logger.info("Cleaning up MeetingManager...")

        # Stop all active meetings
        for meeting_id in list(self.sessions.keys()):
            await self.stop_meeting(meeting_id)

        # Close webhook manager
        if self.webhook_manager:
            await self.webhook_manager.close()

        logger.info("MeetingManager cleanup complete")

    async def start_meeting(self, meeting_url: str, meeting_name: str) -> str:
        """
        Start a new meeting session

        Args:
            meeting_url: Zoom meeting URL
            meeting_name: Name for this meeting

        Returns:
            str: Unique meeting ID
        """
        meeting_id = str(uuid.uuid4())
        logger.info(f"Starting meeting {meeting_id}: {meeting_name}")

        # Create session
        session = MeetingSession(meeting_id, meeting_name, meeting_url)

        # Initialize Zoom bot
        session.zoom_bot = ZoomBot(meeting_url, meeting_id)

        # Initialize transcription service
        if settings.deepgram_api_key:
            session.transcription = TranscriptionService(
                api_key=settings.deepgram_api_key,
                meeting_id=meeting_id,
                on_transcript=lambda segment: self._on_transcript(meeting_id, segment)
            )
        else:
            logger.warning("Deepgram API key not configured - transcription disabled")

        # Store session
        self.sessions[meeting_id] = session

        # Start services asynchronously
        asyncio.create_task(self._start_meeting_services(meeting_id))

        return meeting_id

    async def _start_meeting_services(self, meeting_id: str):
        """
        Start all services for a meeting

        Args:
            meeting_id: Meeting identifier
        """
        session = self.sessions.get(meeting_id)
        if not session:
            logger.error(f"Session {meeting_id} not found")
            return

        try:
            # Join Zoom meeting
            if session.zoom_bot:
                joined = await session.zoom_bot.join_meeting()
                if not joined:
                    logger.error(f"Failed to join Zoom meeting {meeting_id}")
                    return

            # Start transcription
            if session.transcription:
                await session.transcription.start_streaming()

            # Start audio processing pipeline
            if session.zoom_bot and session.transcription:
                asyncio.create_task(
                    self._audio_processing_loop(meeting_id)
                )

            logger.info(f"All services started for meeting {meeting_id}")

        except Exception as e:
            logger.error(f"Error starting meeting services: {e}")

    async def _audio_processing_loop(self, meeting_id: str):
        """
        Process audio stream from Zoom and send to transcription

        Args:
            meeting_id: Meeting identifier
        """
        session = self.sessions.get(meeting_id)
        if not session or not session.zoom_bot or not session.transcription:
            return

        try:
            logger.info(f"Starting audio processing loop for {meeting_id}")

            async for audio_chunk in session.zoom_bot.get_audio_stream():
                await session.transcription.send_audio(audio_chunk)

        except Exception as e:
            logger.error(f"Error in audio processing loop: {e}")

    async def _on_transcript(self, meeting_id: str, segment: dict):
        """
        Handle new transcript segment

        Args:
            meeting_id: Meeting identifier
            segment: Transcript segment data
        """
        session = self.sessions.get(meeting_id)
        if not session:
            return

        # Update stats
        session.segment_count += 1
        speaker = segment.get("speaker", "unknown")
        session.speaker_stats[speaker] = session.speaker_stats.get(speaker, 0) + 1

        # Send to n8n webhook
        if self.webhook_manager:
            asyncio.create_task(
                self.webhook_manager.send_transcript(segment)
            )

        # Broadcast to WebSocket clients
        await self._broadcast_to_websockets(meeting_id, {
            "type": "transcript_update",
            "data": segment
        })

    async def stop_meeting(self, meeting_id: str):
        """
        Stop a meeting and cleanup resources

        Args:
            meeting_id: Meeting identifier
        """
        session = self.sessions.get(meeting_id)
        if not session:
            logger.warning(f"Meeting {meeting_id} not found")
            return

        logger.info(f"Stopping meeting {meeting_id}")

        # Stop transcription
        if session.transcription:
            await session.transcription.stop_streaming()

        # Leave Zoom meeting
        if session.zoom_bot:
            await session.zoom_bot.leave_meeting()

        # Close WebSocket connections
        for ws in session.websockets:
            try:
                await ws.close()
            except:
                pass

        # Remove session
        del self.sessions[meeting_id]

        logger.info(f"Meeting {meeting_id} stopped")

    async def get_meeting_status(self, meeting_id: str) -> Optional[dict]:
        """
        Get current status of a meeting

        Args:
            meeting_id: Meeting identifier

        Returns:
            dict: Meeting status and statistics
        """
        session = self.sessions.get(meeting_id)
        if not session:
            return None

        return {
            "meeting_id": meeting_id,
            "meeting_name": session.meeting_name,
            "duration_minutes": session.get_duration_minutes(),
            "segment_count": session.segment_count,
            "speaker_stats": session.speaker_stats,
            "zoom_bot_status": session.zoom_bot.get_status() if session.zoom_bot else None,
            "transcription_status": session.transcription.get_status() if session.transcription else None,
            "active_connections": len(session.websockets)
        }

    async def process_command(self, meeting_id: str, command: str) -> dict:
        """
        Process a user command with full meeting context

        Args:
            meeting_id: Meeting identifier
            command: User's command/question

        Returns:
            dict: AI-generated response
        """
        session = self.sessions.get(meeting_id)
        if not session:
            return {
                "response": "Meeting nicht gefunden",
                "suggestions": []
            }

        # Get full transcript
        full_transcript = ""
        if session.transcription:
            full_transcript = session.transcription.get_full_transcript()

        # Build context
        context = {
            "duration_minutes": session.get_duration_minutes(),
            "total_segments": session.segment_count,
            "speaker_distribution": session.speaker_stats
        }

        # Send to n8n
        if self.webhook_manager:
            response = await self.webhook_manager.send_command(
                meeting_id=meeting_id,
                command=command,
                full_transcript=full_transcript,
                context=context
            )

            # Broadcast response to WebSocket clients
            if response:
                await self._broadcast_to_websockets(meeting_id, {
                    "type": "command_response",
                    "data": {
                        "command": command,
                        "response": response
                    }
                })

            return response or {
                "response": "Fehler bei der Verarbeitung",
                "suggestions": []
            }

        return {
            "response": "Webhook Manager nicht verfügbar",
            "suggestions": []
        }

    async def broadcast_suggestions(self, meeting_id: str, suggestions: dict):
        """
        Broadcast AI suggestions to connected clients

        Args:
            meeting_id: Meeting identifier
            suggestions: AI-generated suggestions
        """
        await self._broadcast_to_websockets(meeting_id, {
            "type": "suggestion_update",
            "data": suggestions
        })

    async def register_websocket(self, meeting_id: str, websocket: WebSocket):
        """Register a WebSocket connection for a meeting"""
        session = self.sessions.get(meeting_id)
        if session:
            session.websockets.append(websocket)
            logger.info(f"WebSocket registered for meeting {meeting_id}")

    async def unregister_websocket(self, meeting_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        session = self.sessions.get(meeting_id)
        if session and websocket in session.websockets:
            session.websockets.remove(websocket)
            logger.info(f"WebSocket unregistered for meeting {meeting_id}")

    async def _broadcast_to_websockets(self, meeting_id: str, message: dict):
        """Broadcast message to all connected WebSockets for a meeting"""
        session = self.sessions.get(meeting_id)
        if not session:
            return

        # Send to all connected clients
        disconnected = []
        for ws in session.websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(ws)

        # Remove disconnected clients
        for ws in disconnected:
            session.websockets.remove(ws)
