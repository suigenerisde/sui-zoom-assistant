# Contributing to Zoom Meeting AI Assistant

## Entwicklungs-Workflow

1. **Branch erstellen**
   ```bash
   git checkout -b feature/deine-feature-beschreibung
   ```

2. **Änderungen committen**
   ```bash
   git add .
   git commit -m "Beschreibung der Änderung"
   ```

3. **Push und Pull Request**
   ```bash
   git push origin feature/deine-feature-beschreibung
   ```

## Code-Style

### Python (Backend)
- Folge PEP 8 Guidelines
- Nutze Type Hints wo möglich
- Docstrings für alle Klassen und Funktionen
- Max. 100 Zeichen pro Zeile

### TypeScript/React (Frontend)
- Nutze TypeScript strikt
- Functional Components mit Hooks
- Props-Interfaces definieren
- TailwindCSS für Styling

## Testing

### Backend
```bash
cd backend
pytest
```

### Frontend
```bash
cd frontend
npm test
```

## Commit-Nachrichten

Format:
```
<type>: <kurze Beschreibung>

<detaillierte Beschreibung falls nötig>
```

Typen:
- `feat`: Neue Features
- `fix`: Bug-Fixes
- `docs`: Dokumentation
- `style`: Code-Formatierung
- `refactor`: Code-Refactoring
- `test`: Tests
- `chore`: Maintenance

## Code Review

- Mindestens 1 Approval erforderlich
- Alle Tests müssen grün sein
- Code muss dokumentiert sein
