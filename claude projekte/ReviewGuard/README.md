# ReviewGuard

KI-gestütztes Monitoring- und Moderationssystem für Arztbewertungen (Google, Jameda u.a.).

**Zweck:** Erkennung potenziell problematischer Bewertungen (Beleidigungen, Spam, Fake, Falschaussagen, toxische Sprache) und Unterstützung beim offiziellen Meldeprozess — keine automatischen Löschungen, keine Umgehung von Plattformmechanismen.

---

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Frontend  :3000                                     │
└────────────┬────────────────────────────────────────────────┘
             │ REST
  ┌──────────▼──────────┐   ┌─────────────────────────────┐
  │  Ingestion Service  │──▶│  Moderation Service  :8002   │
  │  :8001              │   │  (Claude / GPT-4o)           │
  └──────────┬──────────┘   └──────────┬──────────────────┘
             │                         │
  ┌──────────▼──────────┐   ┌──────────▼──────────────────┐
  │  PostgreSQL  :5432  │   │  Notification Service :8003  │
  └─────────────────────┘   └─────────────────────────────┘
             │
  ┌──────────▼──────────┐
  │  Reporting Service  │
  │  :8004              │
  └─────────────────────┘
```

## Services

| Service      | Port | Funktion                                      |
|--------------|------|-----------------------------------------------|
| ingestion    | 8001 | Reviews erfassen (manuell, CSV, Batch)        |
| moderation   | 8002 | KI-Klassifizierung + Entwurfs-Generator       |
| notification | 8003 | E-Mail-Benachrichtigung bei Hochrisiko-Reviews |
| reporting    | 8004 | PDF / CSV / JSON Export                       |
| frontend     | 3000 | Dashboard (Next.js)                           |

---

## Setup

### 1. Voraussetzungen

- Docker Desktop
- Docker Compose v2
- Anthropic API Key (oder OpenAI API Key)

### 2. Konfiguration

```bash
cp .env.example .env
# Öffne .env und trage ein:
#   ANTHROPIC_API_KEY=sk-ant-...
#   SMTP_USER + SMTP_PASSWORD (optional, für E-Mail-Benachrichtigungen)
```

### 3. Starten

```bash
docker compose up --build
```

Danach:
- **Dashboard:** http://localhost:3000
- **API Ingestion:** http://localhost:8001/docs
- **API Moderation:** http://localhost:8002/docs
- **API Reporting:** http://localhost:8004/docs

---

## Nutzung

### Bewertung hinzufügen (UI)

1. Dashboard → "Bewertungen" → "Bewertung hinzufügen"
2. Plattform wählen, Text einfügen, Speichern
3. KI-Analyse startet automatisch im Hintergrund
4. Ergebnis mit Risiko-Score und Kategorien erscheint in der Karte

### Bewertung hinzufügen (API)

```bash
curl -X POST http://localhost:8001/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "jameda",
    "reviewer_name": "Anonym",
    "rating": 1,
    "content": "Dieser Arzt ist eine absolute Katastrophe..."
  }'
```

### Entwurf generieren

Nach der Analyse: In der Bewertungskarte Entwurfstyp wählen und "Erstellen" klicken.

- **Plattform-Meldung:** Formeller Support-Text für Google/Jameda
- **Antwort-Entwurf:** Professionelle öffentliche Antwort des Arztes
- **Anwalt-Vorlage:** Textvorlage für juristische Prüfung

### Bericht exportieren

"Berichte" → Format wählen → Optional Mindest-Risikoscore setzen → "Bericht erstellen"

---

## KI-Klassifizierungskategorien

| Kategorie        | Bedeutung                                              |
|------------------|--------------------------------------------------------|
| Beleidigung      | Persönliche Beschimpfung des Arztes / Teams            |
| Spam             | Off-Topic, Werbung, repetitiver Content                |
| Fake             | Bot-Muster, erkennbar erfundene Identität              |
| Falschaussage    | Faktisch falscher, überprüfbarer Sachverhalt           |
| Toxisch          | Hasssprache, Drohungen, Diskriminierung                |

Risiko-Score 0–100%:
- **≥65%** → Rot / Hochrisiko → Benachrichtigung + Priorität
- **35–64%** → Amber / Prüfwürdig
- **<35%** → Grün / Unauffällig

---

## Datenschutz (DSGVO)

- Keine Patientendaten werden gespeichert oder verarbeitet
- Bewertungstexte werden nur zur Klassifizierung an die AI-API übermittelt
- Kein Scraping von Plattformen
- Alle Daten verbleiben in der eigenen Infrastruktur (Docker)

---

## Entwicklung (ohne Docker)

```bash
# Backend (je Service):
cd services/ingestion
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend:
cd frontend
npm install
npm run dev
```
