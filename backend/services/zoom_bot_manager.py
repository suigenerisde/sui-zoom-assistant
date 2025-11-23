"""
Zoom Bot Manager Service

Manages the Zoom Meeting SDK Bot - starting, stopping, and controlling meeting sessions.
This service coordinates between the bot container and the audio transcription service.
"""
import asyncio
import logging
import os
import subprocess
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .zoom_bot_audio_service import ZoomBotAudioService

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    """Bot status states."""
    IDLE = "idle"
    STARTING = "starting"
    JOINING = "joining"
    IN_MEETING = "in_meeting"
    TRANSCRIBING = "transcribing"
    LEAVING = "leaving"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MeetingSession:
    """Represents an active meeting session."""
    meeting_id: str
    join_url: str
    display_name: str
    started_at: datetime
    status: BotStatus = BotStatus.IDLE
    transcript_segments: List[Dict[str, Any]] = field(default_factory=list)
    full_transcript: str = ""
    error_message: Optional[str] = None


class ZoomBotManager:
    """
    Manages Zoom Bot instances for meeting transcription.

    This manager:
    - Starts the Zoom Bot container with meeting parameters
    - Coordinates audio capture and transcription
    - Handles bot lifecycle (join, transcribe, leave)
    - Provides status updates via WebSocket
    """

    def __init__(
        self,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status_change: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        socket_path: str = "/tmp/meeting.sock",
    ):
        """
        Initialize the Zoom Bot Manager.

        Args:
            on_transcript: Callback for new transcript segments
            on_status_change: Callback for bot status changes
            socket_path: Unix socket path for audio data
        """
        self.on_transcript = on_transcript
        self.on_status_change = on_status_change
        # Socket path must match C++ SocketServer: /tmp/audio/meeting.sock
        self.socket_path = "/tmp/audio/meeting.sock"

        self.audio_service: Optional[ZoomBotAudioService] = None
        self.current_session: Optional[MeetingSession] = None
        self.bot_process: Optional[subprocess.Popen] = None

        # Environment configuration
        self.zoom_client_id = os.getenv("ZOOM_CLIENT_ID")
        self.zoom_client_secret = os.getenv("ZOOM_CLIENT_SECRET")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

    async def join_meeting(
        self,
        join_url: str,
        display_name: str = "SUI-Assistant",
        meeting_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Join a Zoom meeting and start transcription.

        Args:
            join_url: Zoom meeting join URL
            display_name: Bot display name in meeting
            meeting_id: Optional custom meeting ID (extracted from URL if not provided)

        Returns:
            Dict with status and session info
        """
        if self.current_session and self.current_session.status in [
            BotStatus.IN_MEETING,
            BotStatus.TRANSCRIBING,
            BotStatus.JOINING,
        ]:
            return {
                "success": False,
                "error": "Bot is already in a meeting",
                "session": self._session_to_dict(self.current_session),
            }

        # Extract meeting ID from URL if not provided
        if not meeting_id:
            meeting_id = self._extract_meeting_id(join_url)
            if not meeting_id:
                meeting_id = f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create new session
        self.current_session = MeetingSession(
            meeting_id=meeting_id,
            join_url=join_url,
            display_name=display_name,
            started_at=datetime.now(),
            status=BotStatus.STARTING,
        )

        self._notify_status("starting")

        try:
            # Start the audio service first (listens on socket)
            self.audio_service = ZoomBotAudioService(
                socket_path=self.socket_path,
                deepgram_api_key=self.deepgram_api_key,
                on_transcript=self._handle_transcript,
                on_status_change=self._handle_audio_status,
            )

            if not await self.audio_service.start(meeting_id):
                raise Exception("Failed to start audio service")

            # Start the Zoom Bot (in Docker or directly)
            self.current_session.status = BotStatus.JOINING
            self._notify_status("joining")

            # Set environment variables for the bot
            bot_env = os.environ.copy()
            bot_env["ZOOM_CLIENT_ID"] = self.zoom_client_id or ""
            bot_env["ZOOM_CLIENT_SECRET"] = self.zoom_client_secret or ""
            bot_env["ZOOM_JOIN_URL"] = join_url

            # Start the Zoom Bot container with the join URL
            # The zoom-bot container is already running, we use docker exec to start the bot
            zoom_bot_container = self._find_zoom_bot_container()
            if zoom_bot_container:
                logger.info(f"Starting Zoom Bot in container {zoom_bot_container}")
                try:
                    # Execute the run command in the zoom-bot container
                    cmd = [
                        "docker", "exec",
                        "-e", f"ZOOM_JOIN_URL={join_url}",
                        "-d",  # Detached mode
                        zoom_bot_container,
                        "/bin/bash", "-c",
                        "cd /app && ./build/release/zoomsdk "
                        f"--client-id={self.zoom_client_id} "
                        f"--client-secret={self.zoom_client_secret} "
                        f"--join-url={join_url}"
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info("Zoom Bot started successfully")
                    else:
                        logger.error(f"Failed to start Zoom Bot: {result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.warning("Docker exec timed out - bot may still be starting")
                except Exception as e:
                    logger.error(f"Error starting Zoom Bot: {e}")
            else:
                logger.warning("Zoom Bot container not found - bot will not join meeting")
                logger.info("Make sure zoom-bot container is running via docker-compose")

            self.current_session.status = BotStatus.TRANSCRIBING
            self._notify_status("transcribing")

            return {
                "success": True,
                "message": "Bot joining meeting",
                "session": self._session_to_dict(self.current_session),
            }

        except Exception as e:
            logger.error(f"Error joining meeting: {e}")
            self.current_session.status = BotStatus.ERROR
            self.current_session.error_message = str(e)
            self._notify_status("error")

            # Cleanup
            if self.audio_service:
                await self.audio_service.stop()
                self.audio_service = None

            return {
                "success": False,
                "error": str(e),
                "session": self._session_to_dict(self.current_session),
            }

    async def leave_meeting(self) -> Dict[str, Any]:
        """
        Leave the current meeting and stop transcription.

        Returns:
            Dict with status and final transcript
        """
        if not self.current_session:
            return {
                "success": False,
                "error": "No active meeting session",
            }

        self.current_session.status = BotStatus.LEAVING
        self._notify_status("leaving")

        try:
            # Get final transcript before stopping
            final_transcript = ""
            if self.audio_service:
                final_transcript = self.audio_service.get_transcript()
                await self.audio_service.stop()
                self.audio_service = None

            # Stop bot process if running
            if self.bot_process:
                self.bot_process.terminate()
                self.bot_process = None

            self.current_session.status = BotStatus.STOPPED
            self.current_session.full_transcript = final_transcript
            self._notify_status("stopped")

            session_data = self._session_to_dict(self.current_session)
            self.current_session = None

            return {
                "success": True,
                "message": "Left meeting successfully",
                "session": session_data,
                "transcript": final_transcript,
            }

        except Exception as e:
            logger.error(f"Error leaving meeting: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _handle_transcript(self, segment: Dict[str, Any]):
        """Handle incoming transcript segment."""
        if self.current_session:
            self.current_session.transcript_segments.append(segment)

        # Forward to external callback
        if self.on_transcript:
            try:
                if asyncio.iscoroutinefunction(self.on_transcript):
                    asyncio.create_task(self.on_transcript(segment))
                else:
                    self.on_transcript(segment)
            except Exception as e:
                logger.error(f"Error in transcript callback: {e}")

    def _handle_audio_status(self, status: str):
        """Handle audio service status changes."""
        logger.info(f"Audio service status: {status}")

        if status == "bot_connected" and self.current_session:
            self.current_session.status = BotStatus.TRANSCRIBING
            self._notify_status("transcribing")
        elif status == "bot_disconnected" and self.current_session:
            self.current_session.status = BotStatus.STOPPED
            self._notify_status("stopped")

    def _notify_status(self, status: str):
        """Notify external listeners of status change."""
        if self.on_status_change and self.current_session:
            try:
                data = self._session_to_dict(self.current_session)
                if asyncio.iscoroutinefunction(self.on_status_change):
                    asyncio.create_task(self.on_status_change(status, data))
                else:
                    self.on_status_change(status, data)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _session_to_dict(self, session: MeetingSession) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "meeting_id": session.meeting_id,
            "join_url": session.join_url,
            "display_name": session.display_name,
            "started_at": session.started_at.isoformat(),
            "status": session.status.value,
            "transcript_segments_count": len(session.transcript_segments),
            "error_message": session.error_message,
        }

    def _extract_meeting_id(self, join_url: str) -> Optional[str]:
        """Extract meeting ID from Zoom URL."""
        import re
        # Match patterns like /j/123456789 or /s/123456789
        match = re.search(r'/[js]/(\d+)', join_url)
        if match:
            return match.group(1)
        return None

    def _find_zoom_bot_container(self) -> Optional[str]:
        """Find the running zoom-bot container name."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=zoom-bot", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                container_name = result.stdout.strip().split('\n')[0]
                logger.info(f"Found zoom-bot container: {container_name}")
                return container_name
        except Exception as e:
            logger.error(f"Error finding zoom-bot container: {e}")
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current bot manager status."""
        return {
            "has_active_session": self.current_session is not None,
            "session": (
                self._session_to_dict(self.current_session)
                if self.current_session
                else None
            ),
            "audio_service_status": (
                self.audio_service.get_status()
                if self.audio_service
                else None
            ),
            "credentials_configured": bool(
                self.zoom_client_id and self.zoom_client_secret
            ),
            "deepgram_configured": bool(self.deepgram_api_key),
        }

    def get_transcript(self) -> str:
        """Get current transcript."""
        if self.audio_service:
            return self.audio_service.get_transcript()
        elif self.current_session:
            return self.current_session.full_transcript
        return ""

    def get_transcript_segments(self) -> List[Dict[str, Any]]:
        """Get all transcript segments."""
        if self.current_session:
            return self.current_session.transcript_segments
        return []
