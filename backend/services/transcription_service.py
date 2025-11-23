"""
Transcription Service - Deepgram integration for real-time speech-to-text
"""
import asyncio
import logging
from typing import Optional, Callable, AsyncGenerator
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Deepgram SDK v3 imports
DeepgramClient = None
LiveTranscriptionEvents = None
LiveOptions = None

def _get_deepgram():
    """Lazy load Deepgram SDK v3"""
    global DeepgramClient, LiveTranscriptionEvents, LiveOptions
    if DeepgramClient is None:
        try:
            from deepgram import DeepgramClient as DGClient, LiveTranscriptionEvents as LTE, LiveOptions as LO
            DeepgramClient = DGClient
            LiveTranscriptionEvents = LTE
            LiveOptions = LO
        except (ImportError, SyntaxError) as e:
            logger.warning(f"Deepgram SDK not available: {e}")
            return None
    return DeepgramClient


class TranscriptionService:
    """
    Real-time transcription service using Deepgram API

    Handles WebSocket connection to Deepgram and processes audio streams
    into text transcriptions with speaker diarization and timestamps
    """

    def __init__(
        self,
        api_key: str,
        meeting_id: str,
        on_transcript: Optional[Callable] = None
    ):
        """
        Initialize Transcription Service

        Args:
            api_key: Deepgram API key
            meeting_id: Unique meeting identifier
            on_transcript: Callback function for transcript events
        """
        DGClient = _get_deepgram()
        if not DGClient:
            raise ImportError("Deepgram SDK not available")

        self.api_key = api_key
        self.meeting_id = meeting_id
        self.on_transcript = on_transcript

        self.dg_client = DGClient(api_key)
        self.connection = None
        self.is_streaming = False

        # Transcript tracking
        self.segment_number = 0
        self.transcript_buffer = []
        self.max_buffer_size = 10

        logger.info(f"Initialized Transcription Service for meeting {meeting_id}")

    async def start_streaming(self):
        """
        Initialize Deepgram WebSocket connection for streaming transcription

        Configures Deepgram with optimal settings for German language
        and sales conversation context
        """
        try:
            logger.info("Starting Deepgram streaming connection")

            # Deepgram SDK v3 options
            options = LiveOptions(
                model="nova-2",
                language="de",
                smart_format=True,
                interim_results=True,
                utterance_end_ms=1000,
                vad_events=True,
                encoding="linear16",
                sample_rate=16000,
                channels=1,
            )

            # Create live connection (SDK v3 API)
            self.connection = self.dg_client.listen.live.v("1")

            # Set up event handlers
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_message)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)

            # Start connection
            if await self.connection.start(options):
                self.is_streaming = True
                logger.info("Deepgram streaming connection established")
            else:
                logger.error("Failed to start Deepgram connection")
                self.is_streaming = False

        except Exception as e:
            logger.error(f"Failed to start Deepgram streaming: {e}")
            self.is_streaming = False
            raise

    def _on_open(self, *args, **kwargs):
        """Handle connection open event"""
        logger.info("Deepgram WebSocket connection opened")

    def _on_error(self, *args, **kwargs):
        """Handle error event"""
        error = kwargs.get('error') or (args[1] if len(args) > 1 else "Unknown error")
        logger.error(f"Deepgram error: {error}")

    async def send_audio(self, audio_chunk: bytes):
        """
        Send audio chunk to Deepgram for transcription

        Args:
            audio_chunk: Audio data in PCM format (16kHz, mono)
        """
        if not self.is_streaming or not self.connection:
            logger.warning("Cannot send audio: Streaming not active")
            return

        try:
            await self.connection.send(audio_chunk)
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")

    def _on_message(self, *args, **kwargs):
        """
        Handle incoming transcription results from Deepgram SDK v3

        Args:
            args/kwargs: Deepgram event data
        """
        try:
            # SDK v3: result is in kwargs or args[1]
            result = kwargs.get('result') or (args[1] if len(args) > 1 else None)

            if result is None:
                return

            # Get channel and alternatives
            channel = result.channel
            alternatives = channel.alternatives

            if not alternatives:
                return

            transcript = alternatives[0].transcript

            if not transcript or not transcript.strip():
                return

            is_final = result.is_final
            speech_final = result.speech_final
            confidence = alternatives[0].confidence if hasattr(alternatives[0], 'confidence') else 0.0

            # Only process final transcripts for production use
            if not is_final:
                logger.debug(f"Interim result: {transcript}")
                return

            # Get speaker information if available
            words = alternatives[0].words if hasattr(alternatives[0], 'words') else []
            speaker = None
            if words and hasattr(words[0], 'speaker'):
                speaker = f"speaker_{words[0].speaker}"

            # Create transcript segment
            segment = {
                "meeting_id": self.meeting_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "speaker": speaker or "unknown",
                "segment": transcript,
                "segment_number": self.segment_number,
                "is_final": is_final,
                "confidence": confidence,
                "context": {
                    "previous_segments": self.transcript_buffer[-5:],
                    "duration_seconds": 0
                }
            }

            self.segment_number += 1

            # Add to buffer
            self.transcript_buffer.append(transcript)
            if len(self.transcript_buffer) > self.max_buffer_size:
                self.transcript_buffer.pop(0)

            logger.info(
                f"Transcript #{segment['segment_number']}: "
                f"[{speaker}] {transcript} (confidence: {confidence:.2f})"
            )

            # Call callback if provided
            if self.on_transcript:
                asyncio.create_task(self.on_transcript(segment))

        except Exception as e:
            logger.error(f"Error processing transcription result: {e}")

    def _on_close(self, *args, **kwargs):
        """Handle WebSocket connection close"""
        logger.info("Deepgram WebSocket connection closed")
        self.is_streaming = False

    async def stop_streaming(self):
        """Stop transcription and close WebSocket connection"""
        try:
            logger.info("Stopping Deepgram streaming")

            if self.connection:
                await self.connection.finish()

            self.is_streaming = False
            self.connection = None
            logger.info("Deepgram streaming stopped")

        except Exception as e:
            logger.error(f"Error stopping Deepgram streaming: {e}")

    def get_full_transcript(self) -> str:
        """
        Get the complete transcript buffer

        Returns:
            str: Full transcript text
        """
        return " ".join(self.transcript_buffer)

    def get_status(self) -> dict:
        """
        Get current transcription service status

        Returns:
            dict: Status information
        """
        return {
            "meeting_id": self.meeting_id,
            "is_streaming": self.is_streaming,
            "segment_count": self.segment_number,
            "buffer_size": len(self.transcript_buffer)
        }
