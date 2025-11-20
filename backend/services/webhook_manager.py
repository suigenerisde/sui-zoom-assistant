"""
Webhook Manager - Handles communication with n8n workflows
"""
import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WebhookManager:
    """
    Manages webhook communications with n8n workflows

    Handles:
    - Sending transcripts to n8n for AI analysis
    - Sending user commands with full context
    - Receiving AI-generated suggestions
    """

    def __init__(self, transcript_webhook_url: str, command_webhook_url: str):
        """
        Initialize Webhook Manager

        Args:
            transcript_webhook_url: n8n webhook URL for transcript stream
            command_webhook_url: n8n webhook URL for user commands
        """
        self.transcript_webhook = transcript_webhook_url
        self.command_webhook = command_webhook_url
        self.session: Optional[aiohttp.ClientSession] = None

        logger.info("Initialized Webhook Manager")
        logger.debug(f"Transcript webhook: {transcript_webhook_url}")
        logger.debug(f"Command webhook: {command_webhook_url}")

    async def initialize(self):
        """Initialize aiohttp session"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.info("Webhook Manager session initialized")

    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Webhook Manager session closed")

    async def send_transcript(self, payload: Dict[str, Any]) -> Optional[Dict]:
        """
        Send transcript segment to n8n for AI analysis

        Expected payload format:
        {
            "meeting_id": "unique-meeting-id",
            "timestamp": "2025-01-20T14:30:45.123Z",
            "speaker": "speaker_1",
            "segment": "Das ist der aktuelle Gesprächsabschnitt.",
            "segment_number": 42,
            "is_final": true,
            "confidence": 0.95,
            "context": {
                "previous_segments": ["...", "..."],
                "duration_seconds": 145
            }
        }

        Args:
            payload: Transcript data to send

        Returns:
            dict: Response from n8n workflow, or None if error
        """
        if not self.session:
            await self.initialize()

        try:
            logger.info(
                f"Sending transcript segment #{payload.get('segment_number')} "
                f"to n8n (meeting: {payload.get('meeting_id')})"
            )

            async with self.session.post(
                self.transcript_webhook,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    logger.info("Transcript sent successfully")
                    return response_data
                else:
                    logger.error(
                        f"Error sending transcript: HTTP {response.status} - "
                        f"{response_data}"
                    )
                    return None

        except asyncio.TimeoutError:
            logger.error("Timeout sending transcript to n8n")
            return None
        except Exception as e:
            logger.error(f"Error sending transcript to n8n: {e}")
            return None

    async def send_command(
        self,
        meeting_id: str,
        command: str,
        full_transcript: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict]:
        """
        Send user command with full meeting context to n8n

        Expected payload format:
        {
            "meeting_id": "unique-meeting-id",
            "timestamp": "2025-01-20T14:35:12.456Z",
            "command": "Was sollte ich jetzt fragen?",
            "full_transcript": "Komplettes Transkript bis jetzt...",
            "conversation_context": {
                "duration_minutes": 15,
                "total_segments": 85,
                "speaker_distribution": {
                    "user": 45,
                    "customer": 55
                },
                "key_topics_mentioned": ["Budget", "Timeline", "Team size"]
            }
        }

        Expected response from n8n:
        {
            "response": "Basierend auf dem Gespräch fehlen noch folgende Informationen: ...",
            "suggestions": [
                "Frage nach dem genauen Entscheidungsprozess",
                "Kläre die Timeline für Implementierung"
            ]
        }

        Args:
            meeting_id: Unique meeting identifier
            command: User's question or command
            full_transcript: Complete transcript up to this point
            context: Additional conversation context

        Returns:
            dict: AI-generated response with suggestions, or None if error
        """
        if not self.session:
            await self.initialize()

        payload = {
            "meeting_id": meeting_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "command": command,
            "full_transcript": full_transcript,
            "conversation_context": context or {}
        }

        try:
            logger.info(f"Sending command to n8n (meeting: {meeting_id}): {command}")

            async with self.session.post(
                self.command_webhook,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)  # Longer timeout for AI processing
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    logger.info("Command processed successfully")
                    return response_data
                else:
                    logger.error(
                        f"Error processing command: HTTP {response.status} - "
                        f"{response_data}"
                    )
                    return None

        except asyncio.TimeoutError:
            logger.error("Timeout processing command with n8n")
            return {
                "response": "Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.",
                "suggestions": []
            }
        except Exception as e:
            logger.error(f"Error sending command to n8n: {e}")
            return {
                "response": f"Fehler bei der Verarbeitung: {str(e)}",
                "suggestions": []
            }

    async def health_check(self) -> bool:
        """
        Check if n8n webhooks are reachable

        Returns:
            bool: True if webhooks are healthy, False otherwise
        """
        if not self.session:
            await self.initialize()

        try:
            # Try to ping the transcript webhook (adjust based on n8n setup)
            async with self.session.get(
                self.transcript_webhook.replace("/webhook/", "/ping/"),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status < 500
        except Exception as e:
            logger.warning(f"Webhook health check failed: {e}")
            return False
