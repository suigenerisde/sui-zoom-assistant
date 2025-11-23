"""
Test script for Fireflies Real-Time API
"""
import asyncio
import logging
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from services.fireflies_service import FirefliesService, FirefliesMeetingMonitor

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def on_transcript(segment):
    """Handle transcript segment"""
    print(f"\n{'='*60}")
    print(f"TRANSCRIPT RECEIVED:")
    print(f"  Speaker: {segment.get('speaker', 'Unknown')}")
    print(f"  Text: {segment.get('segment', '')}")
    print(f"  Segment #: {segment.get('segment_number', 0)}")
    print(f"  Source: {segment.get('context', {}).get('source', 'unknown')}")
    print(f"{'='*60}\n")


async def on_connection_status(status):
    """Handle connection status changes"""
    print(f"\n*** CONNECTION STATUS: {status} ***\n")


async def test_active_meetings():
    """Test querying active meetings"""
    api_key = os.getenv("FIREFLIES_API_KEY")
    if not api_key:
        print("ERROR: FIREFLIES_API_KEY not set")
        return None

    print(f"API Key (first 8 chars): {api_key[:8]}...")

    service = FirefliesService(
        api_key=api_key,
        meeting_id="test-meeting"
    )

    print("\nQuerying active meetings...")
    meetings = await service.get_active_meetings()

    if meetings:
        print(f"\nFound {len(meetings)} active meeting(s):")
        for m in meetings:
            print(f"  - ID: {m.get('id')}")
            print(f"    Title: {m.get('title', 'No title')}")
            print(f"    Organizer: {m.get('organizer_email', 'Unknown')}")
            print(f"    Link: {m.get('meeting_link', 'N/A')}")
            print()
        return meetings[0].get('id') if meetings else None
    else:
        print("No active meetings found.")
        print("Note: You need to have Fred (Fireflies bot) in an active meeting.")
        return None


async def test_realtime_connection(transcript_id: str):
    """Test real-time WebSocket connection"""
    api_key = os.getenv("FIREFLIES_API_KEY")

    print(f"\nConnecting to transcript: {transcript_id}")

    service = FirefliesService(
        api_key=api_key,
        meeting_id="test-meeting",
        on_transcript=on_transcript,
        on_connection_status=on_connection_status
    )

    try:
        await service.connect(transcript_id)
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        await service.disconnect()
    except Exception as e:
        print(f"Connection error: {e}")
        print(f"\nService status: {service.get_status()}")


async def test_polling_mode(transcript_id: str):
    """Test polling mode directly"""
    api_key = os.getenv("FIREFLIES_API_KEY")

    print(f"\nTesting polling mode for transcript: {transcript_id}")

    service = FirefliesService(
        api_key=api_key,
        meeting_id="test-meeting",
        on_transcript=on_transcript,
        on_connection_status=on_connection_status
    )

    service.fireflies_transcript_id = transcript_id

    # Start polling directly
    await service._start_polling()

    try:
        # Run for 60 seconds
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        await service.disconnect()
        print(f"\nFinal status: {service.get_status()}")


async def test_meeting_monitor():
    """Test meeting monitor that auto-detects meetings"""
    api_key = os.getenv("FIREFLIES_API_KEY")

    async def on_meeting_found(meeting):
        print(f"\n*** NEW MEETING DETECTED ***")
        print(f"Title: {meeting.get('title', 'No title')}")
        print(f"ID: {meeting.get('id')}")
        print(f"Organizer: {meeting.get('organizer_email')}")

    monitor = FirefliesMeetingMonitor(
        api_key=api_key,
        on_meeting_found=on_meeting_found,
        poll_interval=5
    )

    print("Starting meeting monitor... (press Ctrl+C to stop)")
    await monitor.start_monitoring()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await monitor.stop_monitoring()


async def main():
    """Main test function"""
    print("=" * 60)
    print("Fireflies Real-Time API Test")
    print("=" * 60)

    print("\nOptions:")
    print("1. Query active meetings")
    print("2. Connect to real-time API (requires active meeting)")
    print("3. Test polling mode (requires transcript ID)")
    print("4. Start meeting monitor")
    print("5. Auto: Query meetings and connect to first one")

    choice = input("\nSelect option (1-5): ").strip()

    if choice == "1":
        await test_active_meetings()

    elif choice == "2":
        transcript_id = input("Enter transcript ID: ").strip()
        if transcript_id:
            await test_realtime_connection(transcript_id)
        else:
            print("No transcript ID provided")

    elif choice == "3":
        transcript_id = input("Enter transcript ID: ").strip()
        if transcript_id:
            await test_polling_mode(transcript_id)
        else:
            print("No transcript ID provided")

    elif choice == "4":
        await test_meeting_monitor()

    elif choice == "5":
        transcript_id = await test_active_meetings()
        if transcript_id:
            print(f"\nAttempting to connect to transcript: {transcript_id}")
            await test_realtime_connection(transcript_id)
        else:
            print("\nNo active meeting to connect to.")
            print("Start a meeting with Fred (Fireflies bot) first.")

    else:
        print("Invalid option")


if __name__ == "__main__":
    asyncio.run(main())
