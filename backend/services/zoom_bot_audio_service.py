"""
Zoom Bot Audio Socket Service

Listens on a Unix socket for raw audio data from the Zoom Meeting SDK Bot
and forwards it to Deepgram for live transcription.
"""
import asyncio
import logging
import os
import socket
from typing import Optional, Callable, Dict, Any

from .deepgram_service import DeepgramTranscriptionService

logger = logging.getLogger(__name__)


class ZoomBotAudioService:
    """
    Service that receives audio from the Zoom Bot via Unix socket
    and forwards it to Deepgram for transcription.
    """

    def __init__(
        self,
        socket_path: str = "/tmp/meeting.sock",
        deepgram_api_key: Optional[str] = None,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Zoom Bot Audio Service.

        Args:
            socket_path: Path to the Unix socket
            deepgram_api_key: API key for Deepgram
            on_transcript: Callback for transcript segments
            on_status_change: Callback for status changes
        """
        self.socket_path = socket_path
        self.deepgram_api_key = deepgram_api_key or os.getenv("DEEPGRAM_API_KEY")
        self.on_transcript = on_transcript
        self.on_status_change = on_status_change

        self.deepgram_service: Optional[DeepgramTranscriptionService] = None
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.is_running = False
        self.current_meeting_id: Optional[str] = None
        self._listen_task: Optional[asyncio.Task] = None

    async def start(self, meeting_id: str) -> bool:
        """
        Start listening for audio from the Zoom Bot.

        Args:
            meeting_id: Meeting identifier for this session

        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning("Audio service already running")
            return False

        self.current_meeting_id = meeting_id

        try:
            # Initialize Deepgram connection
            if not self.deepgram_api_key:
                logger.error("Deepgram API key not configured")
                self._notify_status("error_no_api_key")
                return False

            self.deepgram_service = DeepgramTranscriptionService(
                api_key=self.deepgram_api_key,
                meeting_id=meeting_id,
                on_transcript=self.on_transcript,
                on_connection_status=self._on_deepgram_status,
            )

            if not await self.deepgram_service.connect():
                logger.error("Failed to connect to Deepgram")
                self._notify_status("error_deepgram_connect")
                return False

            # Start Unix socket listener
            self._setup_socket()
            self.is_running = True
            self._listen_task = asyncio.create_task(self._listen_loop())

            logger.info(f"Zoom Bot Audio Service started for meeting {meeting_id}")
            self._notify_status("running")
            return True

        except Exception as e:
            logger.error(f"Error starting audio service: {e}")
            self._notify_status("error")
            return False

    def _setup_socket(self):
        """Set up the Unix socket server."""
        # Remove existing socket file if present
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(1)
        self.server_socket.setblocking(False)

        logger.info(f"Unix socket server listening on {self.socket_path}")

    async def _listen_loop(self):
        """Main loop to accept connections and receive audio data."""
        loop = asyncio.get_event_loop()

        try:
            while self.is_running:
                try:
                    # Accept connection (non-blocking)
                    self.client_socket, _ = await loop.sock_accept(self.server_socket)
                    logger.info("Zoom Bot connected to audio socket")
                    self._notify_status("bot_connected")

                    # Receive audio data
                    await self._receive_audio_loop()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Socket accept error: {e}")
                    await asyncio.sleep(1)  # Retry after error

        except asyncio.CancelledError:
            logger.info("Audio listen loop cancelled")
        finally:
            self._cleanup_socket()

    async def _receive_audio_loop(self):
        """Receive audio data from connected client and forward to Deepgram."""
        loop = asyncio.get_event_loop()
        buffer_size = 4096  # Match Zoom Bot's buffer size

        try:
            while self.is_running and self.client_socket:
                try:
                    # Read audio data (non-blocking)
                    data = await loop.sock_recv(self.client_socket, buffer_size)

                    if not data:
                        logger.info("Zoom Bot disconnected from audio socket")
                        self._notify_status("bot_disconnected")
                        break

                    # Forward to Deepgram
                    if self.deepgram_service and self.deepgram_service.is_connected:
                        await self.deepgram_service.send_audio(data)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio: {e}")
                    break

        finally:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None

    async def stop(self):
        """Stop the audio service."""
        logger.info("Stopping Zoom Bot Audio Service")
        self.is_running = False

        # Cancel listen task
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        # Disconnect from Deepgram
        if self.deepgram_service:
            await self.deepgram_service.disconnect()
            self.deepgram_service = None

        # Cleanup socket
        self._cleanup_socket()

        self._notify_status("stopped")
        logger.info("Zoom Bot Audio Service stopped")

    def _cleanup_socket(self):
        """Clean up socket resources."""
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        # Remove socket file
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except:
                pass

    def _on_deepgram_status(self, status: str):
        """Handle Deepgram status changes."""
        logger.info(f"Deepgram status: {status}")

    def _notify_status(self, status: str):
        """Notify status change via callback."""
        if self.on_status_change:
            try:
                if asyncio.iscoroutinefunction(self.on_status_change):
                    asyncio.create_task(self.on_status_change(status))
                else:
                    self.on_status_change(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "running": self.is_running,
            "meeting_id": self.current_meeting_id,
            "socket_path": self.socket_path,
            "bot_connected": self.client_socket is not None,
            "deepgram_connected": (
                self.deepgram_service.is_connected
                if self.deepgram_service
                else False
            ),
            "deepgram_status": (
                self.deepgram_service.get_status()
                if self.deepgram_service
                else None
            ),
        }

    def get_transcript(self) -> str:
        """Get the full transcript accumulated so far."""
        if self.deepgram_service:
            return self.deepgram_service.get_full_transcript()
        return ""
