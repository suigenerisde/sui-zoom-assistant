"""
Zoom Bot Audio Socket Service

Connects to the Unix socket created by the Zoom Meeting SDK Bot
and forwards audio data to Deepgram for live transcription.
"""
import asyncio
import logging
import os
import socket
import struct
from typing import Optional, Callable, Dict, Any

from .deepgram_service import DeepgramTranscriptionService

logger = logging.getLogger(__name__)


def convert_audio_for_deepgram(
    audio_data: bytes,
    input_sample_rate: int = 32000,
    input_channels: int = 2,
    output_sample_rate: int = 16000,
    output_channels: int = 1
) -> bytes:
    """
    Convert audio from Zoom format to Deepgram format.

    Zoom SDK typically outputs: 32kHz, stereo, 16-bit PCM
    Deepgram expects: 16kHz, mono, 16-bit PCM (linear16)

    Args:
        audio_data: Raw PCM audio bytes (16-bit samples)
        input_sample_rate: Source sample rate (default 32000 for Zoom)
        input_channels: Source channels (default 2 for stereo)
        output_sample_rate: Target sample rate (default 16000 for Deepgram)
        output_channels: Target channels (default 1 for mono)

    Returns:
        Converted audio bytes
    """
    if not audio_data:
        return audio_data

    # Parse 16-bit samples
    num_samples = len(audio_data) // 2
    samples = struct.unpack(f'<{num_samples}h', audio_data)

    # Convert stereo to mono (average channels)
    if input_channels == 2 and output_channels == 1:
        mono_samples = []
        for i in range(0, len(samples), 2):
            if i + 1 < len(samples):
                # Average left and right channels
                mono_samples.append((samples[i] + samples[i + 1]) // 2)
            else:
                mono_samples.append(samples[i])
        samples = mono_samples

    # Downsample if needed (simple decimation - take every Nth sample)
    if input_sample_rate != output_sample_rate:
        ratio = input_sample_rate // output_sample_rate
        if ratio > 1:
            samples = samples[::ratio]

    # Pack back to bytes
    return struct.pack(f'<{len(samples)}h', *samples)


class ZoomBotAudioService:
    """
    Service that connects to the Zoom Bot's socket server,
    receives audio data, and forwards it to Deepgram for transcription.

    The Zoom Bot (C++) creates a Unix socket server at /tmp/audio/meeting.sock
    This service acts as a CLIENT that connects to that socket.
    """

    def __init__(
        self,
        socket_path: str = "/tmp/audio/meeting.sock",
        deepgram_api_key: Optional[str] = None,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Zoom Bot Audio Service.

        Args:
            socket_path: Path to the Unix socket (created by Zoom Bot)
            deepgram_api_key: API key for Deepgram
            on_transcript: Callback for transcript segments
            on_status_change: Callback for status changes
        """
        self.socket_path = socket_path
        self.deepgram_api_key = deepgram_api_key or os.getenv("DEEPGRAM_API_KEY")
        self.on_transcript = on_transcript
        self.on_status_change = on_status_change

        self.deepgram_service: Optional[DeepgramTranscriptionService] = None
        self.client_socket: Optional[socket.socket] = None
        self.is_running = False
        self.is_connected = False
        self.current_meeting_id: Optional[str] = None
        self._connect_task: Optional[asyncio.Task] = None

    async def start(self, meeting_id: str) -> bool:
        """
        Start the audio service and connect to the Zoom Bot socket.

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

            # Start connection loop (will keep trying to connect to bot socket)
            self.is_running = True
            self._connect_task = asyncio.create_task(self._connect_loop())

            logger.info(f"Zoom Bot Audio Service started for meeting {meeting_id}")
            self._notify_status("running")
            return True

        except Exception as e:
            logger.error(f"Error starting audio service: {e}")
            self._notify_status("error")
            return False

    async def _connect_loop(self):
        """
        Main loop that connects to the Zoom Bot socket and receives audio.
        Keeps trying to connect until stopped.
        """
        retry_delay = 1  # Start with 1 second delay
        max_retry_delay = 10  # Max 10 seconds between retries

        try:
            while self.is_running:
                try:
                    # Check if socket file exists
                    if not os.path.exists(self.socket_path):
                        logger.debug(f"Socket {self.socket_path} not yet available, waiting...")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, max_retry_delay)
                        continue

                    # Try to connect to the socket
                    logger.info(f"Attempting to connect to Zoom Bot socket: {self.socket_path}")

                    self.client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.client_socket.setblocking(False)

                    loop = asyncio.get_event_loop()
                    await loop.sock_connect(self.client_socket, self.socket_path)

                    logger.info("Connected to Zoom Bot audio socket!")
                    self.is_connected = True
                    self._notify_status("bot_connected")
                    retry_delay = 1  # Reset retry delay on successful connection

                    # Receive audio data
                    await self._receive_audio_loop()

                except ConnectionRefusedError:
                    logger.debug(f"Connection refused, Zoom Bot not ready yet")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                except FileNotFoundError:
                    logger.debug(f"Socket file not found: {self.socket_path}")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Socket connection error: {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                finally:
                    self._close_client_socket()

        except asyncio.CancelledError:
            logger.info("Audio connect loop cancelled")
        finally:
            self._close_client_socket()

    async def _receive_audio_loop(self):
        """Receive audio data from Zoom Bot and forward to Deepgram."""
        loop = asyncio.get_event_loop()
        buffer_size = 4096  # Match Zoom Bot's buffer size
        bytes_received = 0
        chunks_received = 0

        try:
            while self.is_running and self.client_socket:
                try:
                    # Read audio data (non-blocking)
                    data = await loop.sock_recv(self.client_socket, buffer_size)

                    if not data:
                        logger.info("Zoom Bot disconnected from audio socket")
                        logger.info(f"Total audio received: {bytes_received} bytes in {chunks_received} chunks")
                        self.is_connected = False
                        self._notify_status("bot_disconnected")
                        break

                    bytes_received += len(data)
                    chunks_received += 1

                    # Log first chunk and then every 100 chunks
                    if chunks_received == 1 or chunks_received % 100 == 0:
                        logger.info(f"Received audio chunk #{chunks_received}: {len(data)} bytes (total: {bytes_received} bytes)")

                    # Convert audio from Zoom format (32kHz stereo) to Deepgram format (16kHz mono)
                    converted_data = convert_audio_for_deepgram(data)

                    # Forward to Deepgram
                    if self.deepgram_service and self.deepgram_service.is_connected:
                        await self.deepgram_service.send_audio(converted_data)
                    else:
                        logger.warning("Cannot forward audio - Deepgram not connected")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio: {e}")
                    break

        finally:
            self.is_connected = False

    def _close_client_socket(self):
        """Close the client socket."""
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            self.is_connected = False

    async def stop(self):
        """Stop the audio service."""
        logger.info("Stopping Zoom Bot Audio Service")
        self.is_running = False

        # Cancel connect task
        if self._connect_task:
            self._connect_task.cancel()
            try:
                await self._connect_task
            except asyncio.CancelledError:
                pass
            self._connect_task = None

        # Disconnect from Deepgram
        if self.deepgram_service:
            await self.deepgram_service.disconnect()
            self.deepgram_service = None

        # Close socket
        self._close_client_socket()

        self._notify_status("stopped")
        logger.info("Zoom Bot Audio Service stopped")

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
            "bot_connected": self.is_connected,
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
