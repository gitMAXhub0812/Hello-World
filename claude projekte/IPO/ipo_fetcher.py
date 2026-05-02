import json
import requests
from datetime import datetime
from config import DATA_FILE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _normalize(row: dict) -> dict:
    """Bringt Nasdaq-Felder in ein einheitliches Format."""
    return {
        "symbol":   row.get("proposedTickerSymbol", "?"),
        "name":     row.get("companyName", "N/A"),
        "date":     row.get("expectedPriceDate", "N/A"),
        "exchange": row.get("proposedExchange", "N/A"),
        "price":    row.get("proposedSharePrice", "N/A"),
        "shares":   row.get("sharesOffered", "N/A"),
        "status":   row.get("_status", "upcoming"),
    }


def fetch_ipos() -> list[dict]:
    """Holt bevorstehende und kürzlich gepreiste IPOs von der Nasdaq-API (kein Key nötig)."""
    url = "https://api.nasdaq.com/api/ipo/calendar"
    params = {"date": datetime.now().strftime("%Y-%m")}

    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data", {})

    upcoming = data.get("upcoming", {}).get("upcomingTable", {}).get("rows", [])
    priced   = data.get("priced",   {}).get("pricedTable",   {}).get("rows", [])

    for row in upcoming:
        row["_status"] = "upcoming"
    for row in priced:
        row["_status"] = "priced"

    return [_normalize(r) for r in upcoming + priced]


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
