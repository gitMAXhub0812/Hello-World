"""
IPO Tracker - Sucht nach aktuellen Börsengängen (IPOs) im Internet.
Quellen: Yahoo Finance Upcoming IPOs, Nasdaq IPO Calendar, MarketWatch
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_nasdaq_ipos():
    """Holt IPO-Daten vom Nasdaq IPO-Kalender."""
    url = "https://api.nasdaq.com/api/ipo/calendar"
    params = {"date": datetime.now().strftime("%Y-%m")}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ipos = []
        upcoming = data.get("data", {}).get("upcoming", {}).get("upcomingTable", {}).get("rows", [])
        priced   = data.get("data", {}).get("priced",   {}).get("pricedTable",    {}).get("rows", [])
        for row in upcoming:
            ipos.append({
                "name":          row.get("companyName", "N/A"),
                "ticker":        row.get("proposedTickerSymbol", "N/A"),
                "exchange":      row.get("proposedExchange", "N/A"),
                "price_range":   row.get("proposedSharePrice", "N/A"),
                "shares":        row.get("sharesOffered", "N/A"),
                "expected_date": row.get("expectedPriceDate", "N/A"),
                "status":        "upcoming",
                "source":        "Nasdaq",
            })
        for row in priced:
            ipos.append({
                "name":          row.get("companyName", "N/A"),
                "ticker":        row.get("proposedTickerSymbol", "N/A"),
                "exchange":      row.get("proposedExchange", "N/A"),
                "price_range":   row.get("proposedSharePrice", "N/A"),
                "shares":        row.get("sharesOffered", "N/A"),
                "expected_date": row.get("expectedPriceDate", "N/A"),
                "status":        "priced",
                "source":        "Nasdaq",
            })
        return ipos
    except Exception as e:
        print(f"[Nasdaq] Fehler: {e}")
        return []


def fetch_yahoo_ipos():
    """Holt IPO-Daten von Yahoo Finance."""
    url = "https://finance.yahoo.com/calendar/ipo"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        ipos = []
        rows = soup.select("table tbody tr")
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) >= 4:
                ipos.append({
                    "name":        cols[0],
                    "ticker":      cols[1] if len(cols) > 1 else "N/A",
                    "exchange":    cols[2] if len(cols) > 2 else "N/A",
                    "price_range": cols[3] if len(cols) > 3 else "N/A",
                    "status":      "calendar",
                    "source":      "Yahoo Finance",
                })
        return ipos
    except Exception as e:
        print(f"[Yahoo Finance] Fehler: {e}")
        return []


def fetch_marketwatch_ipos():
    """Holt IPO-Daten von MarketWatch."""
    url = "https://www.marketwatch.com/tools/ipo-calendar"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        ipos = []
        rows = soup.select("table.table--primary tbody tr")
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) >= 4:
                ipos.append({
                    "name":     cols[0],
                    "exchange": cols[1] if len(cols) > 1 else "N/A",
                    "price":    cols[2] if len(cols) > 2 else "N/A",
                    "date":     cols[3] if len(cols) > 3 else "N/A",
                    "status":   "marketwatch",
                    "source":   "MarketWatch",
                })
        return ipos
    except Exception as e:
        print(f"[MarketWatch] Fehler: {e}")
        return []


def display_ipos(ipos: list[dict]) -> None:
    if not ipos:
        print("Keine IPO-Daten gefunden.")
        return
    print(f"\n{'='*70}")
    print(f"  IPO-TRACKER  |  Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*70}")
    for i, ipo in enumerate(ipos, 1):
        print(f"\n[{i}] {ipo.get('name', 'N/A')}")
        for key, value in ipo.items():
            if key != "name" and value not in ("N/A", "", None):
                label = key.replace("_", " ").capitalize()
                print(f"     {label:<18}: {value}")
    print(f"\n{'='*70}")
    print(f"  Gesamt: {len(ipos)} IPOs gefunden")
    print(f"{'='*70}\n")


def save_results(ipos: list[dict], path: str = "ipo_results.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "ipos": ipos}, f, ensure_ascii=False, indent=2)
    print(f"Ergebnisse gespeichert: {path}")


def main():
    print("Suche nach aktuellen Börsengängen (IPOs)...")

    all_ipos = []

    print("\n[1/3] Abrufen von Nasdaq...")
    nasdaq = fetch_nasdaq_ipos()
    all_ipos.extend(nasdaq)
    print(f"      {len(nasdaq)} IPOs gefunden.")

    print("[2/3] Abrufen von Yahoo Finance...")
    yahoo = fetch_yahoo_ipos()
    all_ipos.extend(yahoo)
    print(f"      {len(yahoo)} IPOs gefunden.")

    print("[3/3] Abrufen von MarketWatch...")
    mw = fetch_marketwatch_ipos()
    all_ipos.extend(mw)
    print(f"      {len(mw)} IPOs gefunden.")

    display_ipos(all_ipos)
    save_results(all_ipos)


if __name__ == "__main__":
    main()
