import json
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import FINNHUB_API_KEY, DATA_FILE, LOOKAHEAD_MONTHS


def fetch_ipos() -> list[dict]:
    """Holt bevorstehende IPOs von der Finnhub API."""
    if not FINNHUB_API_KEY:
        raise ValueError(
            "Kein API-Key gefunden. Bitte .env Datei anlegen (siehe .env.example)."
        )

    date_from = datetime.today().strftime("%Y-%m-%d")
    date_to   = (datetime.today() + relativedelta(months=LOOKAHEAD_MONTHS)).strftime("%Y-%m-%d")

    url = "https://finnhub.io/api/v1/calendar/ipo"
    params = {"from": date_from, "to": date_to, "token": FINNHUB_API_KEY}

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()

    return resp.json().get("ipoCalendar", [])


def load_stored_ipos() -> list[dict]:
    """Lädt gespeicherte IPOs aus der lokalen JSON-Datei."""
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ipos(ipos: list[dict]) -> None:
    """Speichert IPO-Liste in die lokale JSON-Datei."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(ipos, f, ensure_ascii=False, indent=2)


def find_new_ipos(stored: list[dict], fetched: list[dict]) -> list[dict]:
    """Gibt IPOs zurück, die in fetched, aber nicht in stored sind."""
    known_symbols = {ipo.get("symbol") for ipo in stored}
    return [ipo for ipo in fetched if ipo.get("symbol") not in known_symbols]


def merge_and_save(fetched: list[dict]) -> list[dict]:
    """Führt gespeicherte und neue IPOs zusammen, speichert und gibt Neue zurück."""
    stored  = load_stored_ipos()
    new     = find_new_ipos(stored, fetched)
    merged  = {ipo["symbol"]: ipo for ipo in stored + fetched}
    save_ipos(list(merged.values()))
    return new
