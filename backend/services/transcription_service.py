"""
Transcription Service - Deepgram integration for real-time speech-to-text
"""
import asyncio
import logging
from typing import Optional, Callable, AsyncGenerator
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Deepgram requires Python 3.10+ - lazy import to avoid syntax errors on 3.9
Deepgram = None

def _get_deepgram():
    """Lazy load Deepgram SDK - requires Python 3.10+"""
    global Deepgram
    if Deepgram is None:
        try:
            from deepgram import Deepgram as DG
            Deepgram = DG
        except (ImportError, SyntaxError) as e:
            logger.warning(f"Deepgram SDK not available: {e}. Requires Python 3.10+")
            return None
    return Deepgram


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
        DG = _get_deepgram()
        if not DG:
            raise ImportError("Deepgram SDK not available. Requires Python 3.10+")

        self.api_key = api_key
        self.meeting_id = meeting_id
        self.on_transcript = on_transcript

        self.dg_client = DG(api_key)
        self.websocket = None
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

            # Deepgram streaming options
            options = {
                "model": "nova-2",  # Best quality model
                "language": "de",  # German
                "punctuate": True,
                "interim_results": True,  # Get live results before finalization
                "utterances": True,  # Split by utterances/sentences
                "diarize": True,  # Speaker detection
                "smart_format": True,  # Auto-format numbers, dates, etc.
            }

            # Create WebSocket connection
            self.websocket = await self.dg_client.transcription.live(options)

            # Set up event handlers
            self.websocket.registerHandler(
                self.websocket.event.CLOSE,
                lambda _: self._on_close()
            )
            self.websocket.registerHandler(
                self.websocket.event.TRANSCRIPT_RECEIVED,
                lambda data: self._on_message(data)
            )

            self.is_streaming = True
            logger.info("Deepgram streaming connection established")

        except Exception as e:
            logger.error(f"Failed to start Deepgram streaming: {e}")
            self.is_streaming = False
            raise

    async def send_audio(self, audio_chunk: bytes):
        """
        Send audio chunk to Deepgram for transcription

        Args:
            audio_chunk: Audio data in PCM format (16kHz, mono)
        """
        if not self.is_streaming or not self.websocket:
            logger.warning("Cannot send audio: Streaming not active")
            return

        try:
            await self.websocket.send(audio_chunk)
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")

    def _on_message(self, data: dict):
        """
        Handle incoming transcription results from Deepgram

        Args:
            data: Deepgram transcription result
        """
        try:
            # Parse Deepgram response
            transcript_data = json.loads(data) if isinstance(data, str) else data

            # Extract transcript information
            channel = transcript_data.get("channel", {})
            alternatives = channel.get("alternatives", [])

            if not alternatives:
                return

            alternative = alternatives[0]
            transcript = alternative.get("transcript", "").strip()

            if not transcript:
                return

            is_final = transcript_data.get("is_final", False)
            speech_final = transcript_data.get("speech_final", False)
            confidence = alternative.get("confidence", 0.0)

            # Only process final transcripts for production use
            if not is_final:
                logger.debug(f"Interim result: {transcript}")
                return

            # Get speaker information if available
            words = alternative.get("words", [])
            speaker = None
            if words and "speaker" in words[0]:
                speaker = f"speaker_{words[0]['speaker']}"

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
                    "duration_seconds": 0  # TODO: Track actual duration
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

    def _on_close(self):
        """Handle WebSocket connection close"""
        logger.info("Deepgram WebSocket connection closed")
        self.is_streaming = False

    async def stop_streaming(self):
        """Stop transcription and close WebSocket connection"""
        try:
            logger.info("Stopping Deepgram streaming")

            if self.websocket:
                await self.websocket.finish()

            self.is_streaming = False
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
