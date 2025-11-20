# Zoom Meeting AI Assistant - Implementation Guide for Claude Code

## Projekt-Übersicht

Entwickle einen intelligenten Zoom-Meeting-Assistenten, der als Bot an Meetings teilnimmt, in Echtzeit transkribiert und über n8n-Webhooks KI-gestützte Unterstützung während des Gesprächs bietet.

**Primärer Use Case:** Verkaufsgespräche, Beratungstermine, Discovery Calls

---

## Technologie-Stack

### Backend
- **Python 3.11+** mit FastAPI
- **Zoom Meeting SDK** (oder Zoom API)
- **Deepgram API** für Echtzeit-Transkription
- **WebSocket** für Live-Updates an Frontend
- **Redis** (optional) für Session-Management
- **SQLite/PostgreSQL** (optional) für Meeting-History

### Frontend
- **React** oder **Next.js**
- **WebSocket Client** für Echtzeit-Updates
- **TailwindCSS** für Styling

### Deployment
- **Docker** Container
- **Coolify** auf Hostinger VPS
- **Caddy** als Reverse Proxy

### Externe Integrationen
- **n8n** für KI-Analyse-Workflows
- **Claude API** (via n8n) für Gesprächsanalyse

---

## System-Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    Zoom Meeting                         │
│                         ↓                               │
│              ┌──────────────────┐                       │
│              │  Zoom Bot Service │                       │
│              │  (Python/FastAPI) │                       │
│              └──────────────────┘                       │
│                      ↓                                  │
│              ┌──────────────────┐                       │
│              │ Audio Processing │                       │
│              │  & Buffering     │                       │
│              └──────────────────┘                       │
│                      ↓                                  │
│              ┌──────────────────┐                       │
│              │ Deepgram API     │                       │
│              │ (Transkription)  │                       │
│              └──────────────────┘                       │
│                      ↓                                  │
│         ┌────────────┴────────────┐                    │
│         ↓                         ↓                    │
│  ┌──────────────┐        ┌──────────────┐             │
│  │ n8n Webhook  │        │  WebSocket   │             │
│  │ (Transkript) │        │    Server    │             │
│  └──────────────┘        └──────────────┘             │
│         ↓                         ↓                    │
│  ┌──────────────┐        ┌──────────────┐             │
│  │ Claude API   │        │  Web UI      │             │
│  │ (Analyse)    │        │  (React)     │             │
│  └──────────────┘        └──────────────┘             │
│         ↓                         ↑                    │
│  ┌──────────────┐                │                    │
│  │ n8n Webhook  │────────────────┘                    │
│  │ (Vorschläge) │                                     │
│  └──────────────┘                                     │
└─────────────────────────────────────────────────────────┘
```

---

## MVP Funktionalitäten (Phase 1-3)

### Phase 1: Core Bot & Transkription
1. ✅ Zoom Bot kann Meeting beitreten (via Meeting-Link)
2. ✅ Audio-Stream erfassen
3. ✅ Deepgram Echtzeit-Transkription
4. ✅ Transkripte an n8n Webhook senden
5. ✅ Basis Web-UI für Monitoring

### Phase 2: KI-Analyse Integration
1. ✅ n8n Workflow empfängt Transkripte
2. ✅ Claude analysiert Gesprächsverlauf
3. ✅ Generierung von Vorschlägen (offene Fragen, nächste Schritte)
4. ✅ Vorschläge zurück an UI via WebSocket/Polling

### Phase 3: Command-System
1. ✅ User-Input-Feld für Commands
2. ✅ Commands an separaten n8n Webhook
3. ✅ Kontext-bewusste Antworten
4. ✅ Anzeige in UI

---

## Implementierungs-Details

### 1. Zoom Bot Service

#### 1.1 Zoom SDK Integration

**Aufgabe:** Erstelle einen Python-Service, der als Bot einem Zoom-Meeting beitreten kann.

**Technische Anforderungen:**
- Nutze Zoom Meeting SDK oder Zoom API
- Bot benötigt eigenen Zoom Account (Pro/Business)
- Implementiere Meeting-Join via Meeting-URL oder Meeting-ID + Passwort
- Audio-Stream muss erfasst werden können
- Bot sollte stummgeschaltet sein (kein Audio-Output)

**Zoom API Credentials:**
```python
# Werden später über Environment Variables bereitgestellt
ZOOM_CLIENT_ID = "..."
ZOOM_CLIENT_SECRET = "..."
ZOOM_BOT_JID = "..."  # Bot's Zoom User ID
```

**Erwartetes Verhalten:**
- Bot joined Meeting
- Erfasst Audio-Stream aller Teilnehmer
- Stellt Audio in Chunks bereit (z.B. 2-5 Sekunden Segmente)
- Error-Handling für Meeting-Ende, Netzwerkprobleme

**Hinweise:**
- Zoom Meeting SDK bietet `ZoomSDK` für Python
- Alternative: `zoomus` Python Package
- Für erste Tests: Teste mit lokalem Zoom-Meeting

**Beispiel-Code-Struktur:**
```python
# zoom_bot.py
import asyncio
from zoom_sdk import ZoomSDK

class ZoomBot:
    def __init__(self, meeting_url: str):
        self.meeting_url = meeting_url
        self.sdk = ZoomSDK()
        
    async def join_meeting(self):
        """Join Zoom meeting and start audio capture"""
        pass
    
    async def get_audio_stream(self):
        """Generator that yields audio chunks"""
        pass
    
    async def leave_meeting(self):
        """Clean disconnect from meeting"""
        pass
```

---

#### 1.2 Audio Processing & Buffering

**Aufgabe:** Audio-Chunks vom Zoom-Bot sammeln und für Transkription vorbereiten.

**Technische Anforderungen:**
- Audio-Format: 16kHz, Mono, PCM (oder Format das Deepgram akzeptiert)
- Buffering: 2-5 Sekunden Chunks für kontinuierliche Transkription
- Queue-System für Audio-Chunks (async Queue)
- Optional: Redis für distributed processing

**Beispiel-Code-Struktur:**
```python
# audio_processor.py
import asyncio
from collections import deque

class AudioProcessor:
    def __init__(self):
        self.buffer = deque(maxlen=100)
        
    async def process_audio_chunk(self, audio_data: bytes):
        """Process and buffer audio chunks"""
        # Convert to required format
        # Add to buffer
        pass
    
    async def get_buffered_audio(self):
        """Get audio ready for transcription"""
        pass
```

---

### 2. Transkriptions-Service (Deepgram)

#### 2.1 Deepgram Integration

**Aufgabe:** Echtzeit-Transkription mit Deepgram API.

**Technische Anforderungen:**
- WebSocket-Verbindung zu Deepgram
- Streaming Audio-Input
- Sprachmodell: `nova-2` (best quality)
- Sprache: `de` (Deutsch)
- Features: `punctuation`, `utterances`, `interim_results`

**Deepgram API Key:**
```python
# Environment Variable
DEEPGRAM_API_KEY = "..."
```

**Erwartetes Verhalten:**
- Empfängt kontinuierliche Audio-Chunks
- Sendet Transkripte zurück (inkl. Interim Results für Live-Feedback)
- Speaker Diarization (wer spricht)
- Timestamps für jeden Abschnitt

**Beispiel-Code-Struktur:**
```python
# transcription_service.py
from deepgram import Deepgram
import asyncio

class TranscriptionService:
    def __init__(self, api_key: str):
        self.dg_client = Deepgram(api_key)
        self.websocket = None
        
    async def start_streaming(self):
        """Initialize Deepgram WebSocket connection"""
        pass
    
    async def send_audio(self, audio_chunk: bytes):
        """Send audio to Deepgram for transcription"""
        pass
    
    async def receive_transcripts(self):
        """Generator yielding transcription results"""
        pass
```

**Response Format (Deepgram):**
```json
{
  "channel": {
    "alternatives": [{
      "transcript": "Das ist ein Test",
      "confidence": 0.98,
      "words": [...]
    }]
  },
  "is_final": true,
  "speech_final": true,
  "duration": 2.5
}
```

---

### 3. Webhook Manager & n8n Integration

#### 3.1 Transkript-Stream Webhook

**Aufgabe:** Sende Transkripte inkrementell an n8n Webhook.

**n8n Webhook URL:** 
```
https://n8n.suigeneris.de/webhook/zoom-transcript-stream
```

**Payload Format:**
```json
{
  "meeting_id": "unique-meeting-id",
  "timestamp": "2025-01-20T14:30:45.123Z",
  "speaker": "speaker_1",  // oder Name falls verfügbar
  "segment": "Das ist der aktuelle Gesprächsabschnitt.",
  "segment_number": 42,
  "is_final": true,
  "confidence": 0.95,
  "context": {
    "previous_segments": ["...", "..."],  // letzte 5 Segmente
    "duration_seconds": 145
  }
}
```

**Timing:**
- Sende nur `is_final=true` Transkripte
- Bei langen Pausen (>2 Sekunden) sofort senden
- Maximal alle 10 Sekunden ein Update

**Beispiel-Code:**
```python
# webhook_manager.py
import aiohttp
import asyncio

class WebhookManager:
    def __init__(self, transcript_webhook_url: str, command_webhook_url: str):
        self.transcript_webhook = transcript_webhook_url
        self.command_webhook = command_webhook_url
        self.session = None
        
    async def send_transcript(self, payload: dict):
        """Send transcript to n8n webhook"""
        async with aiohttp.ClientSession() as session:
            async with session.post(self.transcript_webhook, json=payload) as response:
                return await response.json()
    
    async def send_command(self, command: str, context: dict):
        """Send user command to n8n webhook"""
        pass
```

---

#### 3.2 Command Webhook

**Aufgabe:** User-Commands mit vollständigem Kontext an n8n senden.

**n8n Webhook URL:**
```
https://n8n.suigeneris.de/webhook/zoom-user-command
```

**Payload Format:**
```json
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
```

**Response Format (von n8n zurück):**
```json
{
  "response": "Basierend auf dem Gespräch fehlen noch folgende Informationen: ...",
  "suggestions": [
    "Frage nach dem genauen Entscheidungsprozess",
    "Kläre die Timeline für Implementierung"
  ]
}
```

---

### 4. Web UI (User Interface)

#### 4.1 Dashboard Layout

**Aufgabe:** Erstelle ein React-Dashboard für Live-Meeting-Monitoring.

**Komponenten:**

1. **Header**
   - Meeting-Titel
   - Meeting-Dauer (Timer)
   - Status-Indicator (Connected/Recording)

2. **Live-Transkript-Bereich**
   - Scrollbares Transkript
   - Farbcodierung nach Sprecher
   - Timestamps

3. **KI-Vorschläge-Panel**
   - Liste von Vorschlägen
   - Aktualisiert in Echtzeit
   - Icons für Kategorien (Frage, Einwand, nächster Schritt)

4. **Command-Input**
   - Text-Input-Feld
   - Senden-Button
   - Antwort-Bereich darunter

5. **Meeting-Stats (Sidebar)**
   - Gesprächsdauer
   - Redezeit-Verteilung (User vs. Customer)
   - Erkannte Topics

**Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  🎥 Meeting: Verkaufsgespräch Max Mustermann  ⏱ 15:34   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────┐  ┌────────────────────┐   │
│  │  📝 LIVE TRANSKRIPT     │  │  🎯 KI-VORSCHLÄGE  │   │
│  │                         │  │                    │   │
│  │  [14:30] Du:           │  │  • Budget-Frage    │   │
│  │  "Wie hoch ist..."     │  │    noch ausstehend │   │
│  │                         │  │                    │   │
│  │  [14:31] Kunde:        │  │  • Entscheidungs-  │   │
│  │  "Wir haben..."        │  │    prozess unklar  │   │
│  │                         │  │                    │   │
│  │  [Auto-scroll]         │  │  • Pain Point:     │   │
│  │                         │  │    "Zeitverlust"   │   │
│  │                         │  │    → vertiefen!    │   │
│  └─────────────────────────┘  └────────────────────┘   │
│                                                          │
│  💬 COMMAND                                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Was sollte ich jetzt fragen?                     ▶ │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  📊 STATS: ⏱ 15:34  |  🗣 Du: 45% | Kunde: 55%         │
└──────────────────────────────────────────────────────────┘
```

---

#### 4.2 WebSocket Client

**Aufgabe:** Verbindung zum Backend für Echtzeit-Updates.

**Events:**
- `transcript_update` - Neues Transkript-Segment
- `suggestion_update` - Neue KI-Vorschläge
- `command_response` - Antwort auf User-Command
- `meeting_stats` - Aktualisierte Statistiken

**Beispiel React Hook:**
```javascript
// useWebSocket.js
import { useEffect, useState } from 'react';

export const useWebSocket = (url) => {
  const [messages, setMessages] = useState([]);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    const websocket = new WebSocket(url);
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [...prev, data]);
    };
    
    setWs(websocket);
    
    return () => websocket.close();
  }, [url]);

  const sendCommand = (command) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'command', data: command }));
    }
  };

  return { messages, sendCommand };
};
```

---

### 5. FastAPI Backend Server

#### 5.1 API Endpoints

**Aufgabe:** Erstelle FastAPI Server für Meeting-Management und WebSocket-Verbindungen.

**Endpoints:**

1. **POST /api/meeting/start**
   - Body: `{ "meeting_url": "...", "meeting_name": "..." }`
   - Response: `{ "meeting_id": "...", "status": "starting" }`
   - Startet Zoom Bot und Transkription

2. **POST /api/meeting/stop**
   - Body: `{ "meeting_id": "..." }`
   - Stoppt Bot und schließt Verbindungen

3. **GET /api/meeting/{meeting_id}/status**
   - Response: Meeting-Status und Stats

4. **POST /api/command**
   - Body: `{ "meeting_id": "...", "command": "..." }`
   - Sendet Command an n8n und returned Antwort

5. **WebSocket /ws/{meeting_id}**
   - Echtzeit-Updates für Frontend

**Beispiel-Code:**
```python
# main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/meeting/start")
async def start_meeting(meeting_url: str):
    """Start Zoom bot and begin transcription"""
    pass

@app.websocket("/ws/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket connection for real-time updates"""
    await websocket.accept()
    # Handle connection
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

### 6. n8n Workflows

#### 6.1 Workflow: Transkript-Analyse

**Aufgabe:** Analysiere eingehende Transkripte und generiere Vorschläge.

**Workflow-Struktur:**

```
[Webhook Trigger: Transkript]
    ↓
[Function: Kontext zusammenfassen]
    ↓
[HTTP Request: Claude API]
    Prompt: "Analysiere folgendes Verkaufsgespräch:
             {context}
             
             Aktuelles Segment: {segment}
             
             Gib mir:
             1. Welche wichtigen Fragen wurden noch NICHT gestellt?
             2. Welche Pain Points wurden erwähnt?
             3. Was sollte als nächstes gefragt werden?
             
             Format: JSON mit keys: missing_questions, pain_points, next_steps"
    ↓
[Function: Parse JSON Response]
    ↓
[HTTP Request: Zurück an Backend]
    POST http://zoom-bot-api/api/suggestions
    Body: { meeting_id, suggestions }
```

**Claude Prompt Template:**
```
Du bist ein Sales-Coach der ein Verkaufsgespräch in Echtzeit analysiert.

BISHERIGER GESPRÄCHSVERLAUF:
{previous_context}

AKTUELLES SEGMENT:
Sprecher: {speaker}
Text: {segment}

AUFGABE:
Analysiere das Gespräch und gib mir:

1. FEHLENDE INFORMATIONEN: Welche kritischen Fragen wurden noch nicht gestellt?
   (Budget, Timeline, Entscheidungsprozess, Stakeholder, etc.)

2. PAIN POINTS: Welche Probleme/Herausforderungen hat der Kunde erwähnt?

3. NÄCHSTE SCHRITTE: Was sollte jetzt konkret gefragt oder angesprochen werden?

Antworte AUSSCHLIESSLICH in diesem JSON-Format:
{
  "missing_questions": ["...", "..."],
  "pain_points": ["...", "..."],
  "next_steps": ["...", "..."]
}
```

---

#### 6.2 Workflow: Command-Verarbeitung

**Workflow-Struktur:**

```
[Webhook Trigger: User Command]
    ↓
[Function: Lade kompletten Kontext]
    ↓
[HTTP Request: Claude API]
    Prompt: "User fragt: {command}
             
             Kontext: {full_transcript}
             
             Gib eine präzise, handlungsorientierte Antwort"
    ↓
[Function: Format Response]
    ↓
[Webhook Response: Zurück an Caller]
```

**Beispiel Commands:**
- "Was sollte ich jetzt fragen?"
- "Welche Einwände wurden noch nicht behandelt?"
- "Gib mir eine Zusammenfassung der Pain Points"
- "Hat der Kunde Budget-Interesse gezeigt?"
- "Welche Informationen fehlen für ein Angebot?"

---

### 7. Docker & Deployment

#### 7.1 Dockerfile (Backend)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt:**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
aiohttp==3.9.1
deepgram-sdk==3.0.0
python-multipart==0.0.6
pydantic==2.5.0
redis==5.0.1
python-dotenv==1.0.0

# Zoom SDK (wenn verfügbar via pip, sonst manuell)
# zoomus==1.1.5
```

---

#### 7.2 Docker Compose

```yaml
version: '3.8'

services:
  zoom-bot-api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ZOOM_CLIENT_ID=${ZOOM_CLIENT_ID}
      - ZOOM_CLIENT_SECRET=${ZOOM_CLIENT_SECRET}
      - DEEPGRAM_API_KEY=${DEEPGRAM_API_KEY}
      - N8N_TRANSCRIPT_WEBHOOK=${N8N_TRANSCRIPT_WEBHOOK}
      - N8N_COMMAND_WEBHOOK=${N8N_COMMAND_WEBHOOK}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://zoom-bot-api:8000
    depends_on:
      - zoom-bot-api
    restart: unless-stopped
```

---

#### 7.3 Environment Variables

```bash
# .env
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_BOT_JID=your_bot_jid

DEEPGRAM_API_KEY=your_deepgram_api_key

N8N_TRANSCRIPT_WEBHOOK=https://n8n.suigeneris.de/webhook/zoom-transcript-stream
N8N_COMMAND_WEBHOOK=https://n8n.suigeneris.de/webhook/zoom-user-command

REDIS_URL=redis://redis:6379

# Optional
DATABASE_URL=postgresql://user:pass@localhost/zoom_meetings
```

---

### 8. Testing & Debugging

#### 8.1 Test-Szenarien

**Phase 1 Tests:**
1. Lokales Zoom-Meeting erstellen
2. Bot joined erfolgreich
3. Audio wird erfasst
4. Deepgram transkribiert korrekt (Deutsch)
5. Transkripte landen in Console/Logs

**Phase 2 Tests:**
1. n8n Webhook empfängt Daten
2. Claude-Analyse funktioniert
3. Vorschläge sind relevant und hilfreich

**Phase 3 Tests:**
1. Command-Input funktioniert
2. Antworten sind kontextbezogen
3. UI zeigt alles korrekt an

#### 8.2 Debug-Logs

Implementiere strukturiertes Logging:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# In Code:
logger.info(f"Meeting {meeting_id} started")
logger.debug(f"Audio chunk received: {len(audio_data)} bytes")
logger.error(f"Deepgram error: {error}")
```

---

### 9. Erweiterungen (Post-MVP)

**Nach erfolgreichem MVP:**

1. **HubSpot-Integration**
   - Meeting-Notes automatisch in HubSpot Deal schreiben
   - Contact-Properties updaten basierend auf Gespräch
   - Tasks erstellen für Follow-ups

2. **Meeting-Aufzeichnung**
   - Video-Aufzeichnung speichern
   - Transkript-Export als PDF/DOCX
   - Meeting-Summary generieren

3. **Automatische Meeting-Join**
   - Kalender-Integration (Google Calendar)
   - Bot joined automatisch zu geplanten Meetings
   - Pre-Meeting-Briefing aus CRM-Daten

4. **Analytics**
   - Meeting-Performance-Metriken
   - Conversion-Rate-Tracking
   - Best-Practice-Erkennung

5. **Multi-User-Support**
   - Mehrere User können gleichzeitig verschiedene Meetings haben
   - Team-Dashboard
   - Coaching-Features für Sales-Manager

---

## Erste Schritte für Claude Code

### Priorität 1: Zoom Bot Prototype
1. Erstelle Python-Projekt-Struktur
2. Implementiere Basic Zoom Bot (Meeting Join)
3. Audio-Capture testen

### Priorität 2: Deepgram Integration
1. Deepgram Streaming-Client implementieren
2. Audio → Transkript Pipeline testen
3. Interim vs. Final Results handling

### Priorität 3: n8n Webhook
1. Webhook-Manager erstellen
2. Test-Webhook aufsetzen in n8n
3. Payload-Format finalisieren

### Priorität 4: Basic UI
1. React-App mit WebSocket
2. Live-Transkript-Anzeige
3. Command-Input-Field

---

## Hilfreiche Ressourcen

**Zoom:**
- Zoom Meeting SDK: https://developers.zoom.us/docs/meeting-sdk/
- Zoom API Docs: https://developers.zoom.us/docs/api/

**Deepgram:**
- Python SDK: https://developers.deepgram.com/docs/python-sdk
- Streaming API: https://developers.deepgram.com/docs/streaming

**n8n:**
- Webhook Node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- HTTP Request: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/

---

## Erfolgs-Kriterien

**MVP ist erfolgreich wenn:**
1. ✅ Bot kann Zoom-Meeting joinen
2. ✅ Transkription funktioniert in Echtzeit (Deutsch)
3. ✅ Transkripte werden an n8n gesendet
4. ✅ Claude gibt sinnvolle Vorschläge zurück
5. ✅ User sieht Transkript + Vorschläge in UI
6. ✅ Commands funktionieren und geben hilfreiche Antworten

**Qualitäts-Metriken:**
- Transkriptions-Genauigkeit: >90%
- Latenz Transkript → Vorschlag: <5 Sekunden
- System-Uptime während Meeting: 99%+

---

## Support & Fragen

Bei technischen Fragen oder Unklarheiten:
1. Dokumentiere das Problem
2. Checke API-Docs der jeweiligen Services
3. Frage Thilo für Product/Business-Entscheidungen
4. Für n8n-Workflows: Thilo hat Zugriff und kann unterstützen

---

**Viel Erfolg bei der Implementierung! 🚀**
