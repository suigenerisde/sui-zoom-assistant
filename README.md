# Zoom Meeting AI Assistant

KI-gestützter Assistent für Zoom-Meetings mit Echtzeit-Transkription und intelligenten Vorschlägen für Verkaufsgespräche und Beratungstermine.

## Funktionen

- **Echtzeit-Transkription**: Automatische Transkription von Zoom-Meetings mit Deepgram
- **KI-Analyse**: Intelligente Analyse des Gesprächsverlaufs mit Claude AI via n8n
- **Live-Vorschläge**: Echtzeit-Vorschläge für offene Fragen, Pain Points und nächste Schritte
- **Command-System**: Interaktive Befehle zur Gesprächsanalyse während des Meetings
- **Web-Dashboard**: Übersichtliches Dashboard mit Live-Transkript und Statistiken

## Technologie-Stack

### Backend
- Python 3.11+ mit FastAPI
- Deepgram API für Echtzeit-Transkription
- WebSocket für Live-Updates
- Redis für Session-Management

### Frontend
- Next.js 14 mit TypeScript
- TailwindCSS für Styling
- WebSocket Client für Echtzeit-Updates

### Deployment
- Docker & Docker Compose
- Coolify auf Hostinger VPS
- n8n für KI-Workflows

## Projekt-Struktur

```
sui-zoom-assistant/
├── backend/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── zoom_bot.py
│   │   ├── transcription_service.py
│   │   ├── webhook_manager.py
│   │   └── meeting_manager.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── MeetingDashboard.tsx
│   │   ├── StartMeetingForm.tsx
│   │   ├── TranscriptPanel.tsx
│   │   ├── SuggestionsPanel.tsx
│   │   ├── CommandInput.tsx
│   │   ├── MeetingHeader.tsx
│   │   └── MeetingStats.tsx
│   ├── hooks/
│   │   └── useWebSocket.ts
│   ├── lib/
│   │   └── api.ts
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Installation & Setup

### Voraussetzungen

- Docker & Docker Compose
- Node.js 20+ (für lokale Entwicklung)
- Python 3.11+ (für lokale Entwicklung)
- Zoom-Account (Pro/Business) für Bot-Zugriff
- Deepgram API Key
- n8n-Instanz (bereits vorhanden unter n8n.suigeneris.de)

### 1. Repository klonen

```bash
git clone https://github.com/suigenerisde/sui-zoom-assistant.git
cd sui-zoom-assistant
```

### 2. Environment-Variablen einrichten

Kopiere die `.env.example` Dateien und füge deine API-Keys ein:

```bash
# Root-Verzeichnis
cp .env.example .env

# Frontend
cp frontend/.env.example frontend/.env.local
```

Bearbeite die `.env` Datei und füge deine Credentials ein:

```bash
# Zoom Configuration
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_BOT_JID=your_bot_jid

# Deepgram Configuration
DEEPGRAM_API_KEY=your_deepgram_api_key

# n8n Webhooks (bereits konfiguriert)
N8N_TRANSCRIPT_WEBHOOK=https://n8n.suigeneris.de/webhook/zoom-transcript-stream
N8N_COMMAND_WEBHOOK=https://n8n.suigeneris.de/webhook/zoom-user-command
```

### 3. Mit Docker starten

```bash
# Alle Services starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Services stoppen
docker-compose down
```

Die Anwendung ist dann erreichbar unter:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Dokumentation**: http://localhost:8000/docs

### 4. Lokale Entwicklung (optional)

#### Backend

```bash
cd backend

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Auf Windows: venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Server starten
python main.py
```

#### Frontend

```bash
cd frontend

# Dependencies installieren
npm install

# Development Server starten
npm run dev
```

## API-Endpunkte

### Meeting-Management

- `POST /api/meeting/start` - Startet ein neues Meeting
- `POST /api/meeting/stop` - Beendet ein Meeting
- `GET /api/meeting/{meeting_id}/status` - Meeting-Status abrufen

### Commands

- `POST /api/command` - Sendet einen Command an die KI

### WebSocket

- `WS /ws/{meeting_id}` - WebSocket-Verbindung für Live-Updates

## n8n Workflows

### Transkript-Analyse Workflow

Der Workflow empfängt Transkripte und sendet sie an Claude AI zur Analyse.

**Webhook**: `https://n8n.suigeneris.de/webhook/zoom-transcript-stream`

**Erwartete Funktionen**:
1. Erkennung offener Fragen
2. Identifikation von Pain Points
3. Vorschläge für nächste Schritte

### Command-Verarbeitung Workflow

Der Workflow verarbeitet User-Commands mit vollständigem Meeting-Kontext.

**Webhook**: `https://n8n.suigeneris.de/webhook/zoom-user-command`

**Beispiel-Commands**:
- "Was sollte ich jetzt fragen?"
- "Welche Einwände wurden noch nicht behandelt?"
- "Gib mir eine Zusammenfassung der Pain Points"

## Zoom SDK Integration

**WICHTIG**: Die Zoom Bot Integration ist derzeit als Skeleton implementiert. Für die vollständige Funktionalität muss das Zoom Meeting SDK integriert werden.

### Nächste Schritte für Zoom-Integration:

1. **Zoom App erstellen**:
   - Gehe zu [Zoom Marketplace](https://marketplace.zoom.us/)
   - Erstelle eine "Meeting SDK App" oder "Bot App"
   - Notiere Client ID, Client Secret und Bot JID

2. **SDK Installation**:
   ```bash
   # Prüfe verfügbare Zoom SDKs
   pip search zoom
   # oder verwende offizielle Zoom Meeting SDK Dokumentation
   ```

3. **Implementierung in `backend/services/zoom_bot.py`**:
   - `join_meeting()` Methode vervollständigen
   - `get_audio_stream()` für Audio-Capture implementieren
   - `leave_meeting()` für sauberen Disconnect

## Deployment auf Coolify/Hostinger

1. **Repository mit Coolify verbinden**
2. **Environment-Variablen in Coolify setzen**
3. **Docker Compose als Service konfigurieren**
4. **SSL-Zertifikat mit Caddy einrichten**

## Troubleshooting

### Backend startet nicht

```bash
# Prüfe Logs
docker-compose logs backend

# Prüfe Environment-Variablen
docker-compose config
```

### Frontend kann Backend nicht erreichen

Prüfe die `NEXT_PUBLIC_API_URL` in `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Deepgram-Fehler

Stelle sicher, dass der Deepgram API Key gültig ist:
```bash
# Teste API Key
curl -X POST https://api.deepgram.com/v1/listen \
  -H "Authorization: Token YOUR_API_KEY" \
  -H "Content-Type: audio/wav" \
  --data-binary @test.wav
```

## Entwicklungs-Roadmap

### MVP (Aktuell)
- [x] Backend-Struktur mit FastAPI
- [x] Frontend mit Next.js
- [x] Deepgram Transkriptions-Service
- [x] n8n Webhook-Integration
- [x] WebSocket Live-Updates
- [ ] Zoom SDK Integration
- [ ] n8n Workflows konfigurieren

### Phase 2
- [ ] HubSpot-Integration
- [ ] Meeting-Aufzeichnung
- [ ] PDF/DOCX Export

### Phase 3
- [ ] Automatische Meeting-Join (Kalender-Integration)
- [ ] Multi-User-Support
- [ ] Analytics-Dashboard

## Support

Bei Fragen oder Problemen:
1. Prüfe die Logs: `docker-compose logs -f`
2. Prüfe die API-Dokumentation: http://localhost:8000/docs
3. Kontaktiere Thilo für Product/Business-Entscheidungen

## Lizenz

Proprietär - Sui Generis
