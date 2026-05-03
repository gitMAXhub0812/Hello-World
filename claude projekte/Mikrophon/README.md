# Live Spracherkennung

Desktop-App zur Echtzeit-Transkription per Mikrofon. Läuft vollständig **offline** mit dem Vosk-Modell.

---

## Installation

### 1. Python-Pakete installieren

```bash
pip install -r requirements.txt
```

> **Hinweis für Windows:** Falls `pyaudio` nicht installiert werden kann, lade das passende `.whl`-Paket von https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio herunter und installiere es mit:
> ```bash
> pip install PyAudio‑0.2.14‑cpXX‑cpXX‑win_amd64.whl
> ```
> (`XX` = deine Python-Version, z. B. `310` für Python 3.10)

---

### 2. Deutsches Sprachmodell herunterladen

Das Programm benötigt ein Vosk-Modell für Deutsch. Es gibt zwei Optionen:

| Modell | Größe | Qualität | Link |
|--------|-------|----------|------|
| `vosk-model-small-de-0.15` | ~45 MB | gut, schnell | [Download](https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip) |
| `vosk-model-de-0.21` | ~1,8 GB | sehr gut | [Download](https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip) |

**Empfehlung:** Starte mit dem kleinen Modell.

**Schritte:**
1. ZIP-Datei herunterladen
2. Entpacken
3. Den entpackten Ordner umbenennen in `model`
4. Den `model`-Ordner in denselben Ordner wie `main.py` legen

Die Ordnerstruktur muss so aussehen:
```
Mikrophon/
├── main.py
├── requirements.txt
├── README.md
└── model/
    ├── am/
    ├── graph/
    ├── ivector/
    └── ...
```

---

### 3. Programm starten

```bash
python main.py
```

---

## Bedienung

| Element | Funktion |
|---------|----------|
| **Mikrofon-Dropdown** | Gewünschtes Mikrofon auswählen (↻ zum Aktualisieren) |
| **▶ Aufnahme starten** | Startet die Live-Transkription |
| **⏹ Aufnahme stoppen** | Beendet die Aufnahme |
| **Löschen** | Löscht den gesamten Text |
| **💾 Speichern** | Speichert den Text als `.txt`-Datei |

**Grauer Text** = aktuell erkannte Sprache (noch nicht bestätigt)  
**Schwarzer Text** = bereits bestätigter Text

---

## Mikrofon auswählen

Im Dropdown werden alle verfügbaren Eingabegeräte angezeigt (Format: `Index: Name`).  
Wähle das gewünschte Mikrofon aus, bevor du die Aufnahme startest.  
Mit dem **↻**-Button kannst du die Liste aktualisieren (z. B. nach dem Anschließen eines neuen Geräts).

---

## Anforderungen

- Python 3.8 oder neuer
- Windows / macOS / Linux
- Mikrofon
