"""
Zoom Meeting AI Assistant - Main FastAPI Application
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from typing import Optional
import asyncio

from config.settings import settings
from services.meeting_manager import MeetingManager

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


# Request/Response models
class StartMeetingRequest(BaseModel):
    meeting_url: str
    meeting_name: Optional[str] = "Untitled Meeting"


class StopMeetingRequest(BaseModel):
    meeting_id: str


class CommandRequest(BaseModel):
    meeting_id: str
    command: str


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
