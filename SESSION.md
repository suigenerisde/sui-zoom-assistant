# Session Status - Zoom AI Assistant

## Aktueller Stand (23.11.2024 - Update 14:20)

### Zoom Meeting SDK Bot - IMPLEMENTIERT! ✅

Wir haben einen vollständigen Zoom Meeting SDK Bot implementiert, der:
- Als echter Teilnehmer "SUI-Assistant" Meetings beitritt
- **ALLE Audio-Streams** aufnimmt (deine Stimme + andere Teilnehmer)
- Live-Transkription via Deepgram macht
- Auf deinem VPS via Coolify/Docker läuft

### Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐   Unix Socket    ┌──────────────────┐  │
│  │  zoom-bot       │─────────────────▶│  backend         │  │
│  │  (C++ / Linux)  │  /tmp/meeting    │  (Python/FastAPI)│  │
│  │  "SUI-Assistant"│      .sock       │  + Deepgram      │  │
│  └─────────────────┘                  └────────┬─────────┘  │
│                                                │             │
│                                       ┌────────▼─────────┐  │
│                                       │  frontend        │  │
│                                       │  (Next.js)       │  │
│                                       └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Neue API-Endpunkte

| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/bot/join` | Bot tritt Meeting bei (`join_url`, `display_name`) |
| `POST /api/bot/leave` | Bot verlässt Meeting |
| `GET /api/bot/status` | Aktueller Bot-Status |
| `GET /api/bot/transcript` | Live-Transkript abrufen |

### Neue Dateien

- `zoom-bot/` - Zoom Meeting SDK Bot (C++/Docker)
- `zoom-bot/config.toml` - Bot-Konfiguration (display-name: "SUI-Assistant")
- `backend/services/zoom_bot_audio_service.py` - Audio-Socket-Listener
- `backend/services/zoom_bot_manager.py` - Bot-Steuerung
- `docker-compose.yml` - Aktualisiert mit zoom-bot Service

### Credentials

**WICHTIG:** Der Client Secret wurde versehentlich in den Chat geteilt!
→ Gehe zu https://marketplace.zoom.us/user/build
→ Öffne deine App "Zoom Assistant Bot"
→ Klicke auf "Regenerate" beim Client Secret
→ Aktualisiere `.env` mit dem neuen Secret

Credentials in `.env`:
```
ZOOM_CLIENT_ID=KIqR6fCuRdKOJUvg2sy_sA
ZOOM_CLIENT_SECRET=<NEUER SECRET HIER>
DEEPGRAM_API_KEY=<dein key>
```

## Nächste Schritte

1. **DRINGEND: Zoom Client Secret regenerieren!**
2. Deepgram API Key eintragen (falls nicht vorhanden)
3. Docker testen: `docker-compose up zoom-bot`
4. Meeting beitreten testen via API

## Server starten (Entwicklung)

```bash
# Backend
cd /Users/thilopfeil/Documents/APP-Entwicklung/sui-zoom-assistant/backend
/Users/thilopfeil/Library/Python/3.9/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd /Users/thilopfeil/Documents/APP-Entwicklung/sui-zoom-assistant/frontend
npm run dev
```

## Deployment auf Coolify

```bash
# Im Projekt-Root
docker-compose up -d
```

Die Services werden automatisch gebaut und gestartet.
Ports:
- Backend: 8000
- Frontend: 3000
- Redis: 6379

## Hinweise zum Zoom Bot

- Der Bot erscheint als "SUI-Assistant" im Meeting
- Für **eigene Meetings** (du bist Host/Teilnehmer): Kein Approval nötig!
- Für **fremde Meetings**: Zoom Approval erforderlich (4-6 Wochen)
- Audio wird als PCM 16-bit, 16kHz erfasst
