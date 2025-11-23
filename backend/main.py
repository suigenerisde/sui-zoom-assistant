"""
Zoom Meeting AI Assistant - Main FastAPI Application
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from typing import Optional
import asyncio
import hmac
import hashlib
import aiohttp

from config.settings import settings
from services.meeting_manager import MeetingManager
from services.zoom_bot_manager import ZoomBotManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zoom Meeting AI Assistant",
    description="AI-powered assistant for Zoom meetings with real-time transcription",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Meeting manager instance
meeting_manager = MeetingManager()

# Zoom Bot manager instance (for SDK-based bot)
zoom_bot_manager = ZoomBotManager()


# Request/Response models
class StartMeetingRequest(BaseModel):
    meeting_url: str
    meeting_name: Optional[str] = "Untitled Meeting"


class StopMeetingRequest(BaseModel):
    meeting_id: str


class CommandRequest(BaseModel):
    meeting_id: str
    command: str


class FirefliesConnectRequest(BaseModel):
    transcript_id: str
    meeting_name: Optional[str] = "Fireflies Meeting"


class StartLocalTranscriptionRequest(BaseModel):
    meeting_name: Optional[str] = "Local Transcription"
    device_index: Optional[int] = 0  # BlackHole 2ch (index may vary)
    language: Optional[str] = "de"


class BotJoinRequest(BaseModel):
    """Request to join a meeting with the Zoom SDK Bot"""
    join_url: str
    display_name: Optional[str] = "SUI-Assistant"


class MeetingResponse(BaseModel):
    meeting_id: str
    status: str
    message: Optional[str] = None


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Zoom Meeting AI Assistant",
        "version": "1.0.0"
    }


@app.post("/api/meeting/start", response_model=MeetingResponse)
async def start_meeting(request: StartMeetingRequest):
    """
    Start Zoom bot and begin transcription for a meeting

    Args:
        request: StartMeetingRequest with meeting_url and optional meeting_name

    Returns:
        MeetingResponse with meeting_id and status
    """
    try:
        logger.info(f"Starting meeting: {request.meeting_name}")
        meeting_id = await meeting_manager.start_meeting(
            meeting_url=request.meeting_url,
            meeting_name=request.meeting_name
        )

        return MeetingResponse(
            meeting_id=meeting_id,
            status="starting",
            message=f"Meeting '{request.meeting_name}' is being initialized"
        )
    except Exception as e:
        logger.error(f"Error starting meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/meeting/stop", response_model=MeetingResponse)
async def stop_meeting(request: StopMeetingRequest):
    """
    Stop Zoom bot and end transcription

    Args:
        request: StopMeetingRequest with meeting_id

    Returns:
        MeetingResponse with status
    """
    try:
        logger.info(f"Stopping meeting: {request.meeting_id}")
        await meeting_manager.stop_meeting(request.meeting_id)

        return MeetingResponse(
            meeting_id=request.meeting_id,
            status="stopped",
            message="Meeting stopped successfully"
        )
    except Exception as e:
        logger.error(f"Error stopping meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fireflies/connect", response_model=MeetingResponse)
async def connect_fireflies(request: FirefliesConnectRequest):
    """
    Connect to a Fireflies meeting via Real-Time API

    Use this endpoint to manually connect to an active Fireflies meeting
    by providing the transcript ID.

    Args:
        request: FirefliesConnectRequest with transcript_id and optional meeting_name

    Returns:
        MeetingResponse with meeting_id and status
    """
    try:
        logger.info(f"Connecting to Fireflies meeting: {request.transcript_id}")
        meeting_id = await meeting_manager.start_fireflies_meeting(
            fireflies_transcript_id=request.transcript_id,
            meeting_name=request.meeting_name
        )

        return MeetingResponse(
            meeting_id=meeting_id,
            status="connecting",
            message=f"Connecting to Fireflies meeting '{request.meeting_name}'"
        )
    except Exception as e:
        logger.error(f"Error connecting to Fireflies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/meeting/start-local", response_model=MeetingResponse)
async def start_local_transcription(request: StartLocalTranscriptionRequest):
    """
    Start local transcription using BlackHole + Deepgram

    This endpoint captures audio from BlackHole virtual audio device
    and streams it to Deepgram for real-time transcription.
    Perfect for transcribing YouTube videos, system audio, or Zoom meetings.

    Prerequisites:
    - BlackHole 2ch must be installed and set up as input device
    - System audio must be routed through Multi-Output Device

    Args:
        request: StartLocalTranscriptionRequest with optional meeting_name, device_index, language

    Returns:
        MeetingResponse with meeting_id and status
    """
    try:
        logger.info(f"Starting local transcription: {request.meeting_name}")
        meeting_id = await meeting_manager.start_local_transcription(
            meeting_name=request.meeting_name,
            device_index=request.device_index,
            language=request.language
        )

        return MeetingResponse(
            meeting_id=meeting_id,
            status="transcribing",
            message=f"Local transcription '{request.meeting_name}' started"
        )
    except Exception as e:
        logger.error(f"Error starting local transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fireflies/active-meetings")
async def get_active_fireflies_meetings():
    """
    Get list of active Fireflies meetings

    Returns a list of currently active meetings that can be connected to.

    Returns:
        List of active meeting objects with transcript IDs
    """
    try:
        if not settings.fireflies_api_key:
            raise HTTPException(status_code=400, detail="Fireflies API key not configured")

        from services.fireflies_service import FirefliesService
        service = FirefliesService(
            api_key=settings.fireflies_api_key,
            meeting_id="query"
        )
        meetings = await service.get_active_meetings()
        return {"meetings": meetings}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching active Fireflies meetings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/meeting/{meeting_id}/status")
async def get_meeting_status(meeting_id: str):
    """
    Get current status and statistics for a meeting

    Args:
        meeting_id: Unique meeting identifier

    Returns:
        Meeting status and statistics
    """
    try:
        status = await meeting_manager.get_meeting_status(meeting_id)
        if not status:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meeting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/command")
async def send_command(request: CommandRequest):
    """
    Send a command/question to the AI assistant with full meeting context

    Args:
        request: CommandRequest with meeting_id and command

    Returns:
        AI-generated response with suggestions
    """
    try:
        logger.info(f"Processing command for meeting {request.meeting_id}: {request.command}")
        response = await meeting_manager.process_command(
            meeting_id=request.meeting_id,
            command=request.command
        )
        return response
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggestions")
async def receive_suggestions(meeting_id: str, suggestions: dict):
    """
    Receive AI suggestions from n8n workflow

    This endpoint is called by n8n after analyzing transcripts

    Args:
        meeting_id: Unique meeting identifier
        suggestions: AI-generated suggestions
    """
    try:
        logger.info(f"Received suggestions for meeting {meeting_id}")
        await meeting_manager.broadcast_suggestions(meeting_id, suggestions)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error receiving suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ZOOM SDK BOT ENDPOINTS ====================

@app.post("/api/bot/join")
async def bot_join_meeting(request: BotJoinRequest):
    """
    Join a Zoom meeting with the SDK Bot (SUI-Assistant)

    The bot will join the meeting and start transcribing all audio.
    Unlike local transcription, this captures ALL participants including yourself.

    Args:
        request: BotJoinRequest with join_url and optional display_name

    Returns:
        Session info with meeting_id and status
    """
    try:
        logger.info(f"Bot joining meeting: {request.join_url}")
        result = await zoom_bot_manager.join_meeting(
            join_url=request.join_url,
            display_name=request.display_name
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to join meeting"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining meeting with bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bot/leave")
async def bot_leave_meeting():
    """
    Leave the current meeting and stop transcription

    Returns:
        Final session info with full transcript
    """
    try:
        logger.info("Bot leaving meeting")
        result = await zoom_bot_manager.leave_meeting()

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to leave meeting"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error leaving meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/status")
async def bot_status():
    """
    Get current Zoom Bot status

    Returns:
        Bot status including session info, connection states, and transcript
    """
    try:
        return zoom_bot_manager.get_status()
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/transcript")
async def bot_transcript():
    """
    Get current transcript from the Zoom Bot session

    Returns:
        Full transcript text and segments
    """
    try:
        return {
            "transcript": zoom_bot_manager.get_transcript(),
            "segments": zoom_bot_manager.get_transcript_segments()
        }
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FIREFLIES WEBHOOK ====================

def verify_fireflies_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Fireflies webhook signature using HMAC-SHA256

    Args:
        payload: Raw request body
        signature: Signature from X-Fireflies-Signature header
        secret: Webhook secret key

    Returns:
        True if signature is valid
    """
    if not secret:
        logger.warning("No Fireflies webhook secret configured - skipping signature verification")
        return True

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature or "")


@app.post("/api/webhooks/fireflies")
async def fireflies_webhook(
    request: Request,
    x_fireflies_signature: Optional[str] = Header(None, alias="X-Fireflies-Signature")
):
    """
    Receive webhook notifications from Fireflies

    This endpoint handles:
    - Transcription Completed: When a meeting transcription is ready

    The webhook payload contains the transcript_id which can be used
    to fetch the full transcript via GraphQL API.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature if secret is configured
        if settings.fireflies_webhook_secret:
            if not verify_fireflies_signature(body, x_fireflies_signature, settings.fireflies_webhook_secret):
                logger.warning("Invalid Fireflies webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON payload
        import json
        payload = json.loads(body)

        event_type = payload.get("event", payload.get("type", "unknown"))
        transcript_id = payload.get("transcript_id") or payload.get("transcriptId") or payload.get("data", {}).get("transcript_id")
        meeting_title = payload.get("title") or payload.get("meeting_title") or payload.get("data", {}).get("title", "Unknown Meeting")

        logger.info(f"Received Fireflies webhook: event={event_type}, transcript_id={transcript_id}, title={meeting_title}")

        # Log full payload for debugging
        logger.debug(f"Full webhook payload: {payload}")

        if not transcript_id:
            logger.warning("Webhook received without transcript_id")
            return {"status": "ignored", "reason": "no transcript_id"}

        # Fetch full transcript via GraphQL and forward to n8n
        await process_fireflies_transcript(transcript_id, meeting_title)

        return {
            "status": "success",
            "event": event_type,
            "transcript_id": transcript_id
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Fireflies webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Fireflies webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_fireflies_transcript(transcript_id: str, meeting_title: str):
    """
    Fetch full transcript from Fireflies and forward to n8n

    Args:
        transcript_id: Fireflies transcript ID
        meeting_title: Meeting title for context
    """
    if not settings.fireflies_api_key:
        logger.error("Fireflies API key not configured")
        return

    # GraphQL query to fetch full transcript
    query = """
    query GetTranscript($id: String!) {
        transcript(id: $id) {
            id
            title
            organizer_email
            date
            duration
            meeting_link
            sentences {
                index
                text
                speaker_name
                start_time
                end_time
            }
            summary {
                overview
                action_items
                keywords
            }
        }
    }
    """

    try:
        async with aiohttp.ClientSession() as session:
            # Fetch transcript from Fireflies
            async with session.post(
                "https://api.fireflies.ai/graphql",
                json={"query": query, "variables": {"id": transcript_id}},
                headers={
                    "Authorization": f"Bearer {settings.fireflies_api_key}",
                    "Content-Type": "application/json"
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Failed to fetch transcript: {response.status} - {response_text[:200]}")
                    return

                data = await response.json()

                if "errors" in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return

                transcript = data.get("data", {}).get("transcript")
                if not transcript:
                    logger.warning(f"No transcript data found for {transcript_id}")
                    return

                logger.info(f"Fetched transcript: {transcript.get('title')} with {len(transcript.get('sentences', []))} sentences")

                # Format transcript for n8n
                sentences = transcript.get("sentences", [])
                full_text = " ".join([s.get("text", "") for s in sentences])

                # Build payload for n8n
                n8n_payload = {
                    "source": "fireflies_webhook",
                    "transcript_id": transcript_id,
                    "meeting_title": transcript.get("title", meeting_title),
                    "organizer": transcript.get("organizer_email"),
                    "date": transcript.get("date"),
                    "duration": transcript.get("duration"),
                    "meeting_link": transcript.get("meeting_link"),
                    "full_transcript": full_text,
                    "sentences": sentences,
                    "summary": transcript.get("summary"),
                    "sentence_count": len(sentences)
                }

                # Forward to n8n webhook
                if settings.n8n_transcript_webhook:
                    async with session.post(
                        settings.n8n_transcript_webhook,
                        json=n8n_payload,
                        headers={"Content-Type": "application/json"}
                    ) as n8n_response:
                        if n8n_response.status == 200:
                            logger.info(f"Successfully forwarded transcript to n8n")
                        else:
                            n8n_text = await n8n_response.text()
                            logger.warning(f"n8n response: {n8n_response.status} - {n8n_text[:200]}")

    except Exception as e:
        logger.error(f"Error processing Fireflies transcript: {e}")


@app.websocket("/ws/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket connection for real-time updates

    Provides:
    - transcript_update: New transcript segments
    - suggestion_update: AI-generated suggestions
    - command_response: Responses to user commands
    - meeting_stats: Updated statistics

    Args:
        websocket: WebSocket connection
        meeting_id: Unique meeting identifier
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for meeting {meeting_id}")

    try:
        # Register connection with meeting manager
        await meeting_manager.register_websocket(meeting_id, websocket)

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            # Handle any client-side messages if needed

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for meeting {meeting_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await meeting_manager.unregister_websocket(meeting_id, websocket)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    logger.info("Starting Zoom Meeting AI Assistant...")
    await meeting_manager.initialize()
    logger.info("Application ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down Zoom Meeting AI Assistant...")
    await meeting_manager.cleanup()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Disable in production
        log_level="info"
    )
