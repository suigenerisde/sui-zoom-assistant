"""
Audio Capture Script for Deepgram Live Transcription

This script captures audio from:
1. System audio via BlackHole (for Zoom meetings)
2. Microphone input (for testing)

And sends it to Deepgram for real-time transcription.

Prerequisites:
- pip install pyaudio deepgram-sdk python-dotenv aiohttp
- For system audio: Install BlackHole (https://github.com/ExistentialAudio/BlackHole)

Setup for Zoom Audio Capture:
1. Install BlackHole 2ch from https://existential.audio/blackhole/
2. Open "Audio MIDI Setup" on Mac
3. Create Multi-Output Device with:
   - Your speakers/headphones
   - BlackHole 2ch
4. Set Multi-Output as system output
5. Run this script with --device "BlackHole 2ch"
"""

import asyncio
import argparse
import logging
import os
import sys
import json
from typing import Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

try:
    import pyaudio
except ImportError:
    print("PyAudio not installed. Run: pip install pyaudio")
    print("On Mac: brew install portaudio && pip install pyaudio")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

from services.deepgram_service import DeepgramTranscriptionService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioCapture:
    """
    Captures audio from system or microphone and sends to Deepgram.
    """

    # Audio parameters for Deepgram
    RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK = 1024  # 64ms at 16kHz

    def __init__(
        self,
        device_name: Optional[str] = None,
        meeting_id: Optional[str] = None,
        n8n_webhook: Optional[str] = None,
        language: str = "de"
    ):
        self.device_name = device_name
        self.meeting_id = meeting_id or f"meeting-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.n8n_webhook = n8n_webhook or os.getenv("N8N_TRANSCRIPT_WEBHOOK")
        self.language = language

        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.deepgram: Optional[DeepgramTranscriptionService] = None
        self.running = False
        self.transcript_buffer = []

    def list_devices(self):
        """List all available audio input devices."""
        print("\nAvailable Audio Input Devices:")
        print("=" * 50)

        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  [{i}] {info['name']}")
                print(f"      Channels: {info['maxInputChannels']}, Rate: {info['defaultSampleRate']}")

        print("=" * 50)
        print("\nUsage: python audio_capture.py --device \"Device Name\"")
        print("For BlackHole: python audio_capture.py --device \"BlackHole 2ch\"")

    def find_device_index(self, device_name: str) -> Optional[int]:
        """Find device index by name."""
        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            if device_name.lower() in info['name'].lower() and info['maxInputChannels'] > 0:
                return i
        return None

    async def on_transcript(self, segment: dict):
        """Handle incoming transcript segment."""
        transcript = segment.get("transcript", "")
        is_final = segment.get("is_final", False)

        if is_final:
            # Print final transcript
            print(f"\n>>> {transcript}")
            self.transcript_buffer.append(transcript)

            # Send to n8n webhook if configured
            if self.n8n_webhook:
                await self.send_to_n8n(segment)
        else:
            # Print interim result (overwrite line)
            print(f"... {transcript}", end="\r")

    async def send_to_n8n(self, segment: dict):
        """Send transcript segment to n8n webhook."""
        try:
            payload = {
                "source": "deepgram_live",
                "meeting_id": self.meeting_id,
                "segment_number": segment.get("segment_number", 0),
                "transcript": segment.get("transcript", ""),
                "is_final": segment.get("is_final", False),
                "confidence": segment.get("confidence"),
                "words": segment.get("words", []),
                "timestamp": datetime.now().isoformat(),
                "context": segment.get("context", {})
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.n8n_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"n8n webhook returned {response.status}")

        except Exception as e:
            logger.error(f"Error sending to n8n: {e}")

    def on_status(self, status: str):
        """Handle connection status changes."""
        logger.info(f"Deepgram status: {status}")

    async def start(self):
        """Start audio capture and transcription."""
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            print("Error: DEEPGRAM_API_KEY not set in .env")
            print("Get a free API key at: https://console.deepgram.com/signup")
            return

        # Find audio device
        device_index = None
        if self.device_name:
            device_index = self.find_device_index(self.device_name)
            if device_index is None:
                print(f"Error: Device '{self.device_name}' not found")
                self.list_devices()
                return
            print(f"Using audio device: {self.device_name} (index {device_index})")
        else:
            print("Using default microphone")

        # Initialize Deepgram service
        self.deepgram = DeepgramTranscriptionService(
            api_key=api_key,
            meeting_id=self.meeting_id,
            on_transcript=self.on_transcript,
            on_connection_status=self.on_status,
            language=self.language
        )

        # Connect to Deepgram
        print(f"\nConnecting to Deepgram (Meeting ID: {self.meeting_id})...")
        if not await self.deepgram.connect():
            print("Failed to connect to Deepgram")
            return

        # Open audio stream
        try:
            self.stream = self.pyaudio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            await self.deepgram.disconnect()
            return

        self.running = True
        print("\n" + "=" * 50)
        print("LIVE TRANSCRIPTION ACTIVE")
        print("=" * 50)
        print("Speak now... (Ctrl+C to stop)\n")

        # Capture and send audio
        try:
            while self.running:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    await self.deepgram.send_audio(data)
                    await asyncio.sleep(0.01)  # Small delay to prevent CPU overload
                except OSError as e:
                    if "Input overflowed" in str(e):
                        continue
                    raise

        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            await self.stop()

    async def stop(self):
        """Stop audio capture and cleanup."""
        self.running = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.deepgram:
            await self.deepgram.disconnect()

        self.pyaudio.terminate()

        # Print full transcript
        if self.transcript_buffer:
            print("\n" + "=" * 50)
            print("FULL TRANSCRIPT")
            print("=" * 50)
            print(" ".join(self.transcript_buffer))
            print("=" * 50)

            # Save transcript to file
            filename = f"transcript_{self.meeting_id}.txt"
            with open(filename, "w") as f:
                f.write(" ".join(self.transcript_buffer))
            print(f"\nTranscript saved to: {filename}")


async def main():
    parser = argparse.ArgumentParser(
        description="Capture audio and transcribe with Deepgram"
    )
    parser.add_argument(
        "--device", "-d",
        help="Audio input device name (e.g., 'BlackHole 2ch')"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available audio devices"
    )
    parser.add_argument(
        "--meeting-id", "-m",
        help="Meeting ID for tracking"
    )
    parser.add_argument(
        "--language",
        default="de",
        help="Language code (default: de for German)"
    )
    parser.add_argument(
        "--webhook", "-w",
        help="n8n webhook URL to send transcripts"
    )

    args = parser.parse_args()

    capture = AudioCapture(
        device_name=args.device,
        meeting_id=args.meeting_id,
        n8n_webhook=args.webhook,
        language=args.language
    )

    if args.list:
        capture.list_devices()
        return

    await capture.start()


if __name__ == "__main__":
    asyncio.run(main())
