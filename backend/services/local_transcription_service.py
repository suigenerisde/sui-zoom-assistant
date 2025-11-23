"""
Local Transcription Service - Deepgram with BlackHole audio capture
"""
import asyncio
import logging
import json
from typing import Callable, Optional
from datetime import datetime

import pyaudio
import websockets

logger = logging.getLogger(__name__)


class LocalTranscriptionService:
    """
    Service for local audio transcription via Deepgram

    Captures audio from BlackHole virtual audio device and streams
    to Deepgram for real-time transcription.
    """

    def __init__(
        self,
        api_key: str,
        on_transcript: Callable[[dict], None],
        device_index: int = 2,  # BlackHole 2ch
        sample_rate: int = 48000,
        language: str = "de"
    ):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.language = language

        self._running = False
        self._websocket = None
        self._audio_stream = None
        self._pyaudio = None
        self._tasks = []
        self._full_transcript = []
        self._segment_count = 0

    async def start(self):
        """Start local transcription"""
        if self._running:
            logger.warning("Local transcription already running")
            return

        self._running = True
        self._full_transcript = []
        self._segment_count = 0

        logger.info(f"Starting local transcription with device index {self.device_index}")

        try:
            # Initialize PyAudio
            self._pyaudio = pyaudio.PyAudio()

            # Open audio stream from BlackHole
            self._audio_stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,  # Mono works better
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=4096
            )

            # Connect to Deepgram with diarization enabled
            url = (
                f"wss://api.deepgram.com/v1/listen"
                f"?model=nova-2"
                f"&language={self.language}"
                f"&smart_format=true"
                f"&diarize=true"
                f"&encoding=linear16"
                f"&sample_rate={self.sample_rate}"
                f"&channels=1"
            )

            self._websocket = await websockets.connect(
                url,
                extra_headers={"Authorization": f"Token {self.api_key}"}
            )

            logger.info("Connected to Deepgram WebSocket")

            # Start send and receive tasks
            send_task = asyncio.create_task(self._send_audio())
            receive_task = asyncio.create_task(self._receive_transcripts())

            self._tasks = [send_task, receive_task]

            # Wait for tasks (they run until stopped)
            await asyncio.gather(*self._tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error in local transcription: {e}")
            raise
        finally:
            await self._cleanup()

    async def _send_audio(self):
        """Send audio chunks to Deepgram"""
        logger.info("Starting audio send loop")
        chunk_count = 0

        while self._running and self._websocket and self._audio_stream:
            try:
                # Read audio from BlackHole
                data = self._audio_stream.read(4096, exception_on_overflow=False)

                # Send to Deepgram
                await self._websocket.send(data)

                chunk_count += 1
                if chunk_count % 500 == 0:
                    logger.debug(f"Sent {chunk_count} audio chunks")

                await asyncio.sleep(0.01)

            except Exception as e:
                if self._running:
                    logger.error(f"Error sending audio: {e}")
                break

    async def _receive_transcripts(self):
        """Receive and process transcripts from Deepgram"""
        logger.info("Starting transcript receive loop")

        while self._running and self._websocket:
            try:
                async for message in self._websocket:
                    if not self._running:
                        break

                    try:
                        data = json.loads(message)

                        if "channel" in data:
                            alternatives = data.get("channel", {}).get("alternatives", [{}])
                            transcript = alternatives[0].get("transcript", "")
                            confidence = alternatives[0].get("confidence", 0)
                            is_final = data.get("is_final", False)

                            # Extract speaker from diarization (words have speaker info)
                            words = alternatives[0].get("words", [])
                            speaker_id = 0
                            if words:
                                # Get speaker from first word with speaker info
                                speaker_id = words[0].get("speaker", 0)

                            if transcript:
                                self._segment_count += 1

                                segment = {
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "speaker": f"speaker_{speaker_id}",
                                    "segment": transcript,
                                    "confidence": confidence,
                                    "is_final": is_final
                                }

                                if is_final:
                                    self._full_transcript.append(transcript)

                                # Call callback
                                if self.on_transcript:
                                    await self._safe_callback(segment)

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON from Deepgram: {e}")

            except websockets.exceptions.ConnectionClosed:
                if self._running:
                    logger.warning("Deepgram connection closed")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"Error receiving transcripts: {e}")
                break

    async def _safe_callback(self, segment: dict):
        """Safely call the transcript callback"""
        try:
            result = self.on_transcript(segment)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in transcript callback: {e}")

    async def stop(self):
        """Stop local transcription"""
        logger.info("Stopping local transcription")
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self._cleanup()

    async def _cleanup(self):
        """Clean up resources"""
        # Close WebSocket
        if self._websocket:
            try:
                await self._websocket.close()
            except:
                pass
            self._websocket = None

        # Close audio stream
        if self._audio_stream:
            try:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            except:
                pass
            self._audio_stream = None

        # Terminate PyAudio
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except:
                pass
            self._pyaudio = None

        self._tasks = []
        logger.info("Local transcription cleanup complete")

    def get_full_transcript(self) -> str:
        """Get the full transcript as a single string"""
        return " ".join(self._full_transcript)

    def get_segment_count(self) -> int:
        """Get the number of transcript segments"""
        return self._segment_count

    def get_status(self) -> dict:
        """Get current status"""
        return {
            "running": self._running,
            "connected": self._websocket is not None,
            "segment_count": self._segment_count,
            "device_index": self.device_index
        }
