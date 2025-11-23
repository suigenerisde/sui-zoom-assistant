"""
Fireflies Real-Time API Service - Live transcription via Socket.IO

Connects to Fireflies Real-Time API to receive live transcription events
during active meetings. This eliminates the need for a custom Zoom bot
and audio processing pipeline.

API Documentation: https://docs.fireflies.ai/realtime-api/getting-started
"""
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from enum import Enum

try:
    import socketio
except ImportError:
    socketio = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)


class FirefliesEvent(str, Enum):
    """Fireflies Real-Time API event types"""
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILED = "auth.failed"
    CONNECTION_ESTABLISHED = "connection.established"
    CONNECTION_ERROR = "connection.error"
    TRANSCRIPTION_BROADCAST = "transcription.broadcast"


class ConnectionMode(str, Enum):
    """Connection mode for Fireflies Service"""
    SOCKETIO = "socketio"
    POLLING = "polling"
    DISCONNECTED = "disconnected"


class FirefliesService:
    """
    Fireflies Real-Time API Service for live transcription

    Connects via Socket.IO to receive real-time transcription events
    from Fireflies during active meetings. Falls back to polling if
    Socket.IO connection fails.

    Features:
    - Socket.IO connection with auto-reconnect
    - Automatic fallback to polling mode
    - Token-based authentication
    - Real-time transcription with speaker identification
    - Chunk deduplication via chunk_id
    """

    # Fireflies API endpoints
    GRAPHQL_ENDPOINT = "https://api.fireflies.ai/graphql"
    REALTIME_WS_URL = "wss://api.fireflies.ai"
    REALTIME_WS_PATH = "/ws/realtime"

    # Polling settings
    POLLING_INTERVAL = 3  # seconds between polls

    def __init__(
        self,
        api_key: str,
        meeting_id: str,
        on_transcript: Optional[Callable] = None,
        on_connection_status: Optional[Callable] = None
    ):
        """
        Initialize Fireflies Service

        Args:
            api_key: Fireflies API key
            meeting_id: Internal meeting identifier (for tracking)
            on_transcript: Callback function for transcript events
            on_connection_status: Callback for connection status changes
        """
        if not socketio:
            raise ImportError("python-socketio package not installed. Install with: pip install python-socketio[asyncio_client]")
        if not aiohttp:
            raise ImportError("aiohttp package not installed. Install with: pip install aiohttp")

        self.api_key = api_key
        self.meeting_id = meeting_id
        self.on_transcript = on_transcript
        self.on_connection_status = on_connection_status

        # Socket.IO client
        self.sio: Optional[socketio.AsyncClient] = None
        self.is_connected = False
        self.is_authenticated = False
        self.fireflies_transcript_id: Optional[str] = None
        self.connection_mode = ConnectionMode.DISCONNECTED

        # Polling state
        self._polling_task: Optional[asyncio.Task] = None
        self._last_sentence_index = 0  # Track last processed sentence

        # Transcript tracking
        self.segment_number = 0
        self.transcript_buffer: list[str] = []
        self.max_buffer_size = 50
        self.processed_chunks: set[str] = set()  # For deduplication

        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 5  # seconds

        logger.info(f"Initialized Fireflies Service for meeting {meeting_id}")

    async def get_active_meetings(self) -> list[Dict[str, Any]]:
        """
        Query Fireflies GraphQL API for active meetings

        Returns:
            List of active meeting objects with transcript IDs
        """
        query = """
        query ActiveMeetings {
            active_meetings {
                id
                title
                organizer_email
                meeting_link
                start_time
            }
        }
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.GRAPHQL_ENDPOINT,
                    json={"query": query},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"GraphQL request failed: {response.status} - {response_text[:200]}")
                        return []

                    data = await response.json()

                    if "errors" in data:
                        logger.error(f"GraphQL errors: {data['errors']}")
                        return []

                    meetings = data.get("data", {}).get("active_meetings", [])
                    logger.info(f"Found {len(meetings)} active meetings")
                    return meetings

        except Exception as e:
            logger.error(f"Error fetching active meetings: {e}")
            return []

    async def connect(self, transcript_id: str):
        """
        Connect to Fireflies Real-Time API via Socket.IO

        Args:
            transcript_id: Fireflies transcript ID for the meeting
        """
        self.fireflies_transcript_id = transcript_id

        try:
            logger.info(f"Connecting to Fireflies Real-Time API for transcript {transcript_id}")

            # Create Socket.IO client
            self.sio = socketio.AsyncClient(
                reconnection=True,
                reconnection_attempts=self.max_reconnect_attempts,
                reconnection_delay=self.reconnect_delay,
                logger=False,
                engineio_logger=False
            )

            # Register event handlers
            self._register_event_handlers()

            # Connect with authentication
            # According to Fireflies docs: auth object with token and transcriptId
            await self.sio.connect(
                self.REALTIME_WS_URL,
                socketio_path=self.REALTIME_WS_PATH,
                auth={
                    "token": f"Bearer {self.api_key}",
                    "transcriptId": transcript_id
                },
                transports=["websocket"],
                wait_timeout=10
            )

            self.is_connected = True
            self.connection_mode = ConnectionMode.SOCKETIO
            self.reconnect_attempts = 0

            logger.info("Socket.IO connection established, waiting for auth...")

            # Wait for the connection to be fully established
            # The sio.wait() will keep the connection alive
            await self.sio.wait()

        except socketio.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Fireflies: {e}")
            self.is_connected = False
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"Failed to connect to Fireflies: {type(e).__name__}: {e}")
            self.is_connected = False
            await self._handle_reconnect()

    def _register_event_handlers(self):
        """Register Socket.IO event handlers"""
        if not self.sio:
            return

        @self.sio.event
        async def connect():
            logger.info("Socket.IO connected")
            self.is_connected = True

        @self.sio.event
        async def disconnect():
            logger.warning("Socket.IO disconnected")
            self.is_connected = False
            self.is_authenticated = False

        @self.sio.event
        async def connect_error(data):
            logger.error(f"Socket.IO connection error: {data}")
            self.is_connected = False

        # Fireflies-specific events
        @self.sio.on(FirefliesEvent.AUTH_SUCCESS)
        async def on_auth_success(data):
            await self._on_auth_success(data)

        @self.sio.on(FirefliesEvent.AUTH_FAILED)
        async def on_auth_failed(data):
            await self._on_auth_failed(data)

        @self.sio.on(FirefliesEvent.CONNECTION_ESTABLISHED)
        async def on_connection_established(data):
            await self._on_connection_established(data)

        @self.sio.on(FirefliesEvent.CONNECTION_ERROR)
        async def on_connection_error(data):
            await self._on_connection_error(data)

        @self.sio.on(FirefliesEvent.TRANSCRIPTION_BROADCAST)
        async def on_transcription(data):
            await self._on_transcription(data)

        # Catch-all for unknown events (useful for debugging)
        @self.sio.on("*")
        async def catch_all(event, data):
            logger.debug(f"Received unknown event '{event}': {data}")

    async def _on_auth_success(self, data: dict):
        """Handle successful authentication"""
        self.is_authenticated = True
        logger.info("Fireflies authentication successful")

        if self.on_connection_status:
            await self._safe_callback(
                self.on_connection_status,
                {"status": "authenticated", "meeting_id": self.meeting_id}
            )

    async def _on_auth_failed(self, data: dict):
        """Handle failed authentication"""
        self.is_authenticated = False
        error_msg = data.get("message", "Unknown authentication error") if isinstance(data, dict) else str(data)
        logger.error(f"Fireflies authentication failed: {error_msg}")

        if self.on_connection_status:
            await self._safe_callback(
                self.on_connection_status,
                {"status": "auth_failed", "error": error_msg, "meeting_id": self.meeting_id}
            )

        # Don't reconnect on auth failure - likely invalid credentials
        await self.disconnect()

    async def _on_connection_established(self, data: dict):
        """Handle connection established event"""
        logger.info("Fireflies connection fully established")

        if self.on_connection_status:
            await self._safe_callback(
                self.on_connection_status,
                {"status": "connected", "meeting_id": self.meeting_id}
            )

    async def _on_connection_error(self, data: dict):
        """Handle connection error event"""
        error_msg = data.get("message", "Unknown connection error") if isinstance(data, dict) else str(data)
        logger.error(f"Fireflies connection error: {error_msg}")

        if self.on_connection_status:
            await self._safe_callback(
                self.on_connection_status,
                {"status": "error", "error": error_msg, "meeting_id": self.meeting_id}
            )

    async def _on_transcription(self, data: dict):
        """
        Handle transcription broadcast event

        Args:
            data: Transcription event data from Fireflies

        Expected format (based on Fireflies docs):
        {
            "transcript_id": "...",
            "chunk_id": "...",
            "text": "...",
            "speaker_name": "...",
            "start_time": 10.5,
            "end_time": 12.3
        }
        """
        try:
            # Handle both dict and other formats
            if not isinstance(data, dict):
                logger.warning(f"Unexpected transcription data format: {type(data)}")
                return

            # Extract transcription data
            chunk_id = data.get("chunk_id")
            text = data.get("text", "").strip()
            speaker_name = data.get("speaker_name", "Unknown")
            start_time = data.get("start_time", 0)
            end_time = data.get("end_time", 0)

            if not text:
                return

            # Deduplicate based on chunk_id
            if chunk_id:
                if chunk_id in self.processed_chunks:
                    logger.debug(f"Received update for chunk {chunk_id}")
                    return
                self.processed_chunks.add(chunk_id)

            # Create segment in our standard format
            segment = {
                "meeting_id": self.meeting_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "speaker": speaker_name,
                "segment": text,
                "segment_number": self.segment_number,
                "is_final": True,
                "confidence": 1.0,
                "context": {
                    "previous_segments": self.transcript_buffer[-5:],
                    "start_time": start_time,
                    "end_time": end_time,
                    "fireflies_chunk_id": chunk_id,
                    "fireflies_transcript_id": data.get("transcript_id"),
                    "source": "realtime"
                }
            }

            self.segment_number += 1

            # Add to buffer
            self.transcript_buffer.append(text)
            if len(self.transcript_buffer) > self.max_buffer_size:
                self.transcript_buffer.pop(0)

            logger.info(
                f"Transcript #{segment['segment_number']}: "
                f"[{speaker_name}] {text}"
            )

            # Call callback
            if self.on_transcript:
                await self._safe_callback(self.on_transcript, segment)

        except Exception as e:
            logger.error(f"Error processing transcription: {e}")

    async def _safe_callback(self, callback: Callable, data: Any):
        """Safely execute callback, handling both sync and async functions"""
        try:
            result = callback(data)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in callback: {e}")

    async def _handle_reconnect(self):
        """Handle reconnection logic"""
        if not self.fireflies_transcript_id:
            logger.warning("Cannot reconnect: no transcript ID")
            return

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.warning("Max Socket.IO reconnection attempts reached - switching to polling mode")
            await self._start_polling()
            return

        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts

        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)

        await self.connect(self.fireflies_transcript_id)

    # ==================== POLLING FALLBACK ====================

    async def _start_polling(self):
        """Start polling mode as fallback when Socket.IO fails"""
        if self._polling_task and not self._polling_task.done():
            return  # Already polling

        self.connection_mode = ConnectionMode.POLLING
        self.is_connected = True  # Consider connected in polling mode

        logger.info(f"Starting polling mode for transcript {self.fireflies_transcript_id}")

        if self.on_connection_status:
            await self._safe_callback(
                self.on_connection_status,
                {"status": "polling", "meeting_id": self.meeting_id, "mode": "polling"}
            )

        self._polling_task = asyncio.create_task(self._polling_loop())

    async def _stop_polling(self):
        """Stop polling mode"""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        logger.info("Polling mode stopped")

    async def _polling_loop(self):
        """Main polling loop - fetches transcript updates periodically"""
        logger.info(f"Polling loop started for transcript {self.fireflies_transcript_id}")

        while self.connection_mode == ConnectionMode.POLLING:
            try:
                await self._fetch_transcript_updates()
                await asyncio.sleep(self.POLLING_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(self.POLLING_INTERVAL)

    async def _fetch_transcript_updates(self):
        """Fetch latest transcript data via GraphQL"""
        if not self.fireflies_transcript_id:
            return

        query = """
        query GetTranscript($id: String!) {
            transcript(id: $id) {
                id
                title
                sentences {
                    index
                    text
                    speaker_name
                    start_time
                    end_time
                }
            }
        }
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.GRAPHQL_ENDPOINT,
                    json={
                        "query": query,
                        "variables": {"id": self.fireflies_transcript_id}
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Polling request failed: {response.status} - {response_text[:200]}")
                        return

                    data = await response.json()

                    if "errors" in data:
                        logger.error(f"GraphQL errors: {data['errors']}")
                        return

                    transcript = data.get("data", {}).get("transcript")
                    if not transcript:
                        logger.debug(f"No transcript data in response: {data}")
                        return

                    sentences = transcript.get("sentences") or []
                    if sentences:
                        await self._process_polled_sentences(sentences)
                    else:
                        logger.debug(f"No sentences in transcript yet (title: {transcript.get('title', 'Unknown')})")

        except Exception as e:
            logger.error(f"Error fetching transcript updates: {e}")

    async def _process_polled_sentences(self, sentences: list):
        """Process new sentences from polling"""
        for sentence in sentences:
            index = sentence.get("index", 0)

            # Skip already processed sentences
            if index <= self._last_sentence_index:
                continue

            self._last_sentence_index = index

            text = sentence.get("text", "").strip()
            if not text:
                continue

            speaker_name = sentence.get("speaker_name", "Unknown")
            start_time = sentence.get("start_time", 0)
            end_time = sentence.get("end_time", 0)

            # Create segment in standard format
            segment = {
                "meeting_id": self.meeting_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "speaker": speaker_name,
                "segment": text,
                "segment_number": self.segment_number,
                "is_final": True,
                "confidence": 1.0,
                "context": {
                    "previous_segments": self.transcript_buffer[-5:],
                    "start_time": start_time,
                    "end_time": end_time,
                    "sentence_index": index,
                    "fireflies_transcript_id": self.fireflies_transcript_id,
                    "source": "polling"
                }
            }

            self.segment_number += 1

            # Add to buffer
            self.transcript_buffer.append(text)
            if len(self.transcript_buffer) > self.max_buffer_size:
                self.transcript_buffer.pop(0)

            logger.info(
                f"[POLL] Transcript #{segment['segment_number']}: "
                f"[{speaker_name}] {text}"
            )

            # Call callback
            if self.on_transcript:
                await self._safe_callback(self.on_transcript, segment)

    async def disconnect(self):
        """Disconnect from Fireflies Real-Time API"""
        logger.info("Disconnecting from Fireflies")

        # Stop polling if active
        if self.connection_mode == ConnectionMode.POLLING:
            await self._stop_polling()

        self.is_connected = False
        self.is_authenticated = False
        self.connection_mode = ConnectionMode.DISCONNECTED

        if self.sio:
            try:
                await self.sio.disconnect()
            except Exception as e:
                logger.error(f"Error closing Socket.IO connection: {e}")
            finally:
                self.sio = None

        logger.info("Disconnected from Fireflies")

    def get_full_transcript(self) -> str:
        """
        Get the complete transcript buffer

        Returns:
            str: Full transcript text
        """
        return " ".join(self.transcript_buffer)

    def get_status(self) -> dict:
        """
        Get current service status

        Returns:
            dict: Status information
        """
        return {
            "meeting_id": self.meeting_id,
            "fireflies_transcript_id": self.fireflies_transcript_id,
            "is_connected": self.is_connected,
            "is_authenticated": self.is_authenticated,
            "connection_mode": self.connection_mode.value,
            "segment_count": self.segment_number,
            "buffer_size": len(self.transcript_buffer),
            "reconnect_attempts": self.reconnect_attempts,
            "last_sentence_index": self._last_sentence_index
        }


class FirefliesMeetingMonitor:
    """
    Monitors for active Fireflies meetings and auto-connects

    Polls the Fireflies API for active meetings and automatically
    connects to the Real-Time API when a new meeting is detected.
    """

    def __init__(
        self,
        api_key: str,
        on_meeting_found: Optional[Callable] = None,
        poll_interval: int = 10
    ):
        """
        Initialize Meeting Monitor

        Args:
            api_key: Fireflies API key
            on_meeting_found: Callback when new meeting is detected
            poll_interval: Seconds between API polls
        """
        self.api_key = api_key
        self.on_meeting_found = on_meeting_found
        self.poll_interval = poll_interval

        self.is_monitoring = False
        self.known_meetings: set[str] = set()
        self._monitor_task: Optional[asyncio.Task] = None

    async def start_monitoring(self):
        """Start monitoring for active meetings"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started Fireflies meeting monitor")

    async def stop_monitoring(self):
        """Stop monitoring"""
        self.is_monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped Fireflies meeting monitor")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        service = FirefliesService(self.api_key, "monitor")

        while self.is_monitoring:
            try:
                meetings = await service.get_active_meetings()

                for meeting in meetings:
                    # The active_meetings query returns 'id' as the transcript ID
                    transcript_id = meeting.get("id")

                    if transcript_id and transcript_id not in self.known_meetings:
                        self.known_meetings.add(transcript_id)
                        logger.info(f"New active meeting detected: {meeting.get('title', 'Unknown')}")

                        if self.on_meeting_found:
                            try:
                                result = self.on_meeting_found(meeting)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as e:
                                logger.error(f"Error in meeting found callback: {e}")

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.poll_interval)
