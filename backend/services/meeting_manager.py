"""
Meeting Manager - Orchestrates all meeting-related services
"""
import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING, Any
from datetime import datetime
import uuid
from fastapi import WebSocket

from config.settings import settings
from services.zoom_bot import ZoomBot
from services.webhook_manager import WebhookManager
from services.fireflies_service import FirefliesService, FirefliesMeetingMonitor
from services.local_transcription_service import LocalTranscriptionService

# Lazy import TranscriptionService to avoid Deepgram SDK syntax errors on Python 3.9
# The Deepgram SDK uses match statements which require Python 3.10+
if TYPE_CHECKING:
    from services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)

def _get_transcription_service():
    """Lazy load TranscriptionService to avoid Python 3.9 import issues"""
    try:
        from services.transcription_service import TranscriptionService
        return TranscriptionService
    except (ImportError, SyntaxError) as e:
        logger.warning(f"TranscriptionService not available: {e}")
        return None


class MeetingSession:
    """Represents an active meeting session"""

    def __init__(self, meeting_id: str, meeting_name: str, meeting_url: str):
        self.meeting_id = meeting_id
        self.meeting_name = meeting_name
        self.meeting_url = meeting_url
        self.start_time = datetime.utcnow()

        # Services
        self.zoom_bot: Optional[ZoomBot] = None
        self.transcription: Optional[Any] = None  # TranscriptionService (lazy loaded)
        self.fireflies: Optional[FirefliesService] = None
        self.local_transcription: Optional[LocalTranscriptionService] = None

        # WebSocket connections
        self.websockets: list[WebSocket] = []

        # Stats
        self.segment_count = 0
        self.speaker_stats: Dict[str, int] = {}

        # Fireflies-specific
        self.fireflies_transcript_id: Optional[str] = None

    def get_duration_minutes(self) -> float:
        """Get meeting duration in minutes"""
        delta = datetime.utcnow() - self.start_time
        return delta.total_seconds() / 60


class MeetingManager:
    """
    Central manager for all meeting operations

    Coordinates:
    - Zoom bot lifecycle (legacy) OR Fireflies integration
    - Transcription service (Deepgram or Fireflies)
    - Webhook communications
    - WebSocket connections to frontend
    """

    def __init__(self):
        self.sessions: Dict[str, MeetingSession] = {}
        self.webhook_manager: Optional[WebhookManager] = None
        self.fireflies_monitor: Optional[FirefliesMeetingMonitor] = None
        self.use_fireflies = settings.fireflies_enabled and settings.fireflies_api_key

        logger.info(f"MeetingManager initialized (Fireflies: {self.use_fireflies})")

    async def initialize(self):
        """Initialize manager and dependencies"""
        # Initialize webhook manager
        self.webhook_manager = WebhookManager(
            transcript_webhook_url=settings.n8n_transcript_webhook,
            command_webhook_url=settings.n8n_command_webhook
        )
        await self.webhook_manager.initialize()

        # Initialize Fireflies monitor if enabled
        if self.use_fireflies:
            self.fireflies_monitor = FirefliesMeetingMonitor(
                api_key=settings.fireflies_api_key,
                on_meeting_found=self._on_fireflies_meeting_found,
                poll_interval=settings.fireflies_poll_interval
            )
            await self.fireflies_monitor.start_monitoring()
            logger.info("Fireflies meeting monitor started")

        logger.info("MeetingManager ready")

    async def cleanup(self):
        """Cleanup all active sessions and connections"""
        logger.info("Cleaning up MeetingManager...")

        # Stop Fireflies monitor
        if self.fireflies_monitor:
            await self.fireflies_monitor.stop_monitoring()

        # Stop all active meetings
        for meeting_id in list(self.sessions.keys()):
            await self.stop_meeting(meeting_id)

        # Close webhook manager
        if self.webhook_manager:
            await self.webhook_manager.close()

        logger.info("MeetingManager cleanup complete")

    async def _on_fireflies_meeting_found(self, meeting: dict):
        """
        Callback when Fireflies detects a new active meeting

        Args:
            meeting: Meeting data from Fireflies API
        """
        transcript_id = meeting.get("transcriptId") or meeting.get("id")
        meeting_title = meeting.get("title", "Fireflies Meeting")

        logger.info(f"Auto-connecting to Fireflies meeting: {meeting_title}")

        # Create a new session for this Fireflies meeting
        meeting_id = await self.start_fireflies_meeting(
            fireflies_transcript_id=transcript_id,
            meeting_name=meeting_title
        )

        logger.info(f"Created session {meeting_id} for Fireflies meeting {transcript_id}")

    async def start_local_transcription(
        self,
        meeting_name: str = "Local Transcription",
        device_index: int = 2,  # BlackHole 2ch
        language: str = "de"
    ) -> str:
        """
        Start a local transcription session using BlackHole + Deepgram

        Args:
            meeting_name: Name for this session
            device_index: Audio device index (0 = BlackHole 2ch)
            language: Language code for transcription

        Returns:
            str: Unique meeting ID
        """
        # Get API key - first try settings, then fallback to env file
        api_key = settings.deepgram_api_key
        if not api_key:
            from pathlib import Path
            from dotenv import dotenv_values
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                env_values = dotenv_values(env_file)
                api_key = env_values.get('DEEPGRAM_API_KEY')

        if not api_key:
            raise ValueError("Deepgram API key not configured")

        meeting_id = str(uuid.uuid4())
        logger.info(f"Starting local transcription {meeting_id}: {meeting_name}")

        # Create session
        session = MeetingSession(meeting_id, meeting_name, "local")

        # Initialize local transcription service
        session.local_transcription = LocalTranscriptionService(
            api_key=api_key,
            on_transcript=lambda segment: self._on_transcript(meeting_id, segment),
            device_index=device_index,
            language=language
        )

        # Store session
        self.sessions[meeting_id] = session

        # Start transcription in background
        asyncio.create_task(self._run_local_transcription(meeting_id))

        return meeting_id

    async def _run_local_transcription(self, meeting_id: str):
        """Run local transcription in background"""
        session = self.sessions.get(meeting_id)
        if not session or not session.local_transcription:
            return

        try:
            await session.local_transcription.start()
        except Exception as e:
            logger.error(f"Local transcription error: {e}")
            # Notify connected clients
            await self._broadcast_to_websockets(meeting_id, {
                "type": "error",
                "data": {"message": str(e)}
            })

    async def start_fireflies_meeting(
        self,
        fireflies_transcript_id: str,
        meeting_name: str
    ) -> str:
        """
        Start a meeting session using Fireflies Real-Time API

        Args:
            fireflies_transcript_id: Fireflies transcript ID
            meeting_name: Name for this meeting

        Returns:
            str: Unique meeting ID
        """
        meeting_id = str(uuid.uuid4())
        logger.info(f"Starting Fireflies meeting {meeting_id}: {meeting_name}")

        # Create session
        session = MeetingSession(meeting_id, meeting_name, "")
        session.fireflies_transcript_id = fireflies_transcript_id

        # Initialize Fireflies service
        session.fireflies = FirefliesService(
            api_key=settings.fireflies_api_key,
            meeting_id=meeting_id,
            on_transcript=lambda segment: self._on_transcript(meeting_id, segment),
            on_connection_status=lambda status: self._on_fireflies_status(meeting_id, status)
        )

        # Store session
        self.sessions[meeting_id] = session

        # Connect to Fireflies Real-Time API
        asyncio.create_task(session.fireflies.connect(fireflies_transcript_id))

        return meeting_id

    async def _on_fireflies_status(self, meeting_id: str, status: dict):
        """Handle Fireflies connection status changes"""
        session = self.sessions.get(meeting_id)
        if not session:
            return

        status_type = status.get("status")
        logger.info(f"Fireflies status for {meeting_id}: {status_type}")

        # Broadcast status to connected clients
        await self._broadcast_to_websockets(meeting_id, {
            "type": "connection_status",
            "data": status
        })

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

        # Initialize transcription service (lazy loaded to avoid Python 3.9 issues)
        if settings.deepgram_api_key:
            TranscriptionService = _get_transcription_service()
            if TranscriptionService:
                session.transcription = TranscriptionService(
                    api_key=settings.deepgram_api_key,
                    meeting_id=meeting_id,
                    on_transcript=lambda segment: self._on_transcript(meeting_id, segment)
                )
            else:
                logger.warning("TranscriptionService not available (requires Python 3.10+)")
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

        # Stop local transcription
        if session.local_transcription:
            await session.local_transcription.stop()

        # Stop Fireflies connection
        if session.fireflies:
            await session.fireflies.disconnect()

        # Stop transcription (Deepgram)
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
            "fireflies_status": session.fireflies.get_status() if session.fireflies else None,
            "local_transcription_status": session.local_transcription.get_status() if session.local_transcription else None,
            "transcription_mode": "local" if session.local_transcription else ("fireflies" if session.fireflies else "deepgram"),
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

        # Get full transcript (from Fireflies or Deepgram)
        full_transcript = ""
        if session.fireflies:
            full_transcript = session.fireflies.get_full_transcript()
        elif session.transcription:
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
