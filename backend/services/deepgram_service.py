"""
Deepgram Live Transcription Service

Provides real-time speech-to-text transcription using Deepgram's WebSocket API.
"""
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

logger = logging.getLogger(__name__)


class DeepgramTranscriptionService:
    """
    Real-time transcription service using Deepgram's Live API.

    This service:
    - Connects to Deepgram's WebSocket API
    - Receives audio chunks and sends them to Deepgram
    - Returns live transcription results via callbacks
    """

    def __init__(
        self,
        api_key: str,
        meeting_id: str,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_connection_status: Optional[Callable[[str], None]] = None,
        language: str = "de",  # German default
        model: str = "nova-2",  # Best accuracy model
    ):
        """
        Initialize the Deepgram transcription service.

        Args:
            api_key: Deepgram API key
            meeting_id: Unique meeting identifier for this session
            on_transcript: Callback for transcript segments
            on_connection_status: Callback for connection status changes
            language: Language code (default: "de" for German)
            model: Deepgram model (default: "nova-2" for best accuracy)
        """
        self.api_key = api_key
        self.meeting_id = meeting_id
        self.on_transcript = on_transcript
        self.on_connection_status = on_connection_status
        self.language = language
        self.model = model

        self.client: Optional[DeepgramClient] = None
        self.connection = None
        self.is_connected = False
        self.transcript_buffer = []
        self.segment_count = 0

    async def connect(self) -> bool:
        """
        Connect to Deepgram's Live Transcription API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to Deepgram for meeting {self.meeting_id}")
            self._notify_status("connecting")

            # Initialize Deepgram client
            self.client = DeepgramClient(self.api_key)

            # Configure live transcription options
            options = LiveOptions(
                model=self.model,
                language=self.language,
                smart_format=True,  # Auto-punctuation and formatting
                interim_results=True,  # Get results while speaking
                endpointing=300,  # Detect end of utterance (replaced utterance_end_ms)
                encoding="linear16",
                sample_rate=16000,
                channels=1,
            )

            # Create live connection
            self.connection = self.client.listen.live.v("1")

            # Register event handlers
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)
            self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)

            # Start the connection
            if await self.connection.start(options):
                self.is_connected = True
                logger.info(f"Deepgram connection established for meeting {self.meeting_id}")
                self._notify_status("connected")
                return True
            else:
                logger.error("Failed to start Deepgram connection")
                self._notify_status("failed")
                return False

        except Exception as e:
            logger.error(f"Error connecting to Deepgram: {e}")
            self._notify_status("error")
            return False

    async def send_audio(self, audio_data: bytes) -> bool:
        """
        Send audio data to Deepgram for transcription.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit, 16kHz, mono)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_connected or not self.connection:
            logger.warning("Cannot send audio - not connected")
            return False

        try:
            await self.connection.send(audio_data)
            return True
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Deepgram."""
        if self.connection:
            try:
                await self.connection.finish()
                logger.info(f"Disconnected from Deepgram for meeting {self.meeting_id}")
            except Exception as e:
                logger.error(f"Error disconnecting from Deepgram: {e}")
            finally:
                self.is_connected = False
                self.connection = None
                self._notify_status("disconnected")

    def _on_open(self, *args, **kwargs):
        """Handle connection open event."""
        logger.info("Deepgram WebSocket connection opened")

    def _on_transcript(self, *args, **kwargs):
        """Handle incoming transcript."""
        try:
            # Extract result from kwargs or args
            result = kwargs.get('result') or (args[1] if len(args) > 1 else None)

            if result is None:
                return

            # Get the transcript text
            channel = result.channel
            alternatives = channel.alternatives

            if not alternatives:
                return

            transcript = alternatives[0].transcript

            if not transcript.strip():
                return

            is_final = result.is_final
            speech_final = result.speech_final

            self.segment_count += 1

            # Build transcript segment
            segment = {
                "meeting_id": self.meeting_id,
                "segment_number": self.segment_count,
                "transcript": transcript,
                "is_final": is_final,
                "speech_final": speech_final,
                "confidence": alternatives[0].confidence if hasattr(alternatives[0], 'confidence') else None,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence
                    }
                    for w in (alternatives[0].words or [])
                ] if hasattr(alternatives[0], 'words') else [],
                "context": {
                    "source": "deepgram",
                    "model": self.model,
                    "language": self.language
                }
            }

            # Only log and callback for final results to reduce noise
            if is_final:
                logger.info(f"[Deepgram] Final: {transcript}")
                self.transcript_buffer.append(transcript)
            else:
                logger.debug(f"[Deepgram] Interim: {transcript}")

            # Call transcript callback
            if self.on_transcript:
                self.on_transcript(segment)

        except Exception as e:
            logger.error(f"Error processing Deepgram transcript: {e}")

    def _on_utterance_end(self, *args, **kwargs):
        """Handle end of utterance (speaker finished talking)."""
        logger.debug("Utterance ended")

    def _on_error(self, *args, **kwargs):
        """Handle error event."""
        error = kwargs.get('error') or (args[1] if len(args) > 1 else "Unknown error")
        logger.error(f"Deepgram error: {error}")
        self._notify_status("error")

    def _on_close(self, *args, **kwargs):
        """Handle connection close event."""
        logger.info("Deepgram WebSocket connection closed")
        self.is_connected = False
        self._notify_status("disconnected")

    def _notify_status(self, status: str):
        """Notify status change via callback."""
        if self.on_connection_status:
            try:
                if asyncio.iscoroutinefunction(self.on_connection_status):
                    asyncio.create_task(self.on_connection_status(status))
                else:
                    self.on_connection_status(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "meeting_id": self.meeting_id,
            "connected": self.is_connected,
            "model": self.model,
            "language": self.language,
            "segments_received": self.segment_count,
            "full_transcript": " ".join(self.transcript_buffer)
        }

    def get_full_transcript(self) -> str:
        """Get the full transcript accumulated so far."""
        return " ".join(self.transcript_buffer)


class DeepgramMicrophoneTest:
    """
    Test class for Deepgram with local microphone input.
    Useful for testing the service before integrating with Zoom.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.service: Optional[DeepgramTranscriptionService] = None

    async def start(self):
        """Start microphone test."""
        try:
            import pyaudio
        except ImportError:
            print("PyAudio not installed. Run: pip install pyaudio")
            return

        def on_transcript(segment):
            if segment.get("is_final"):
                print(f"\n>>> {segment['transcript']}")
            else:
                print(f"... {segment['transcript']}", end="\r")

        self.service = DeepgramTranscriptionService(
            api_key=self.api_key,
            meeting_id="mic-test",
            on_transcript=on_transcript,
            on_connection_status=lambda s: print(f"[Status: {s}]")
        )

        if not await self.service.connect():
            print("Failed to connect to Deepgram")
            return

        # Set up microphone
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        print("\nListening... (Ctrl+C to stop)\n")

        try:
            while True:
                data = stream.read(1024, exception_on_overflow=False)
                await self.service.send_audio(data)
                await asyncio.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            await self.service.disconnect()

            print(f"\nFull transcript:\n{self.service.get_full_transcript()}")


# Test script
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("Error: DEEPGRAM_API_KEY not set in .env")
        print("Get a free API key at: https://console.deepgram.com/signup")
        exit(1)

    test = DeepgramMicrophoneTest(api_key)
    asyncio.run(test.start())
