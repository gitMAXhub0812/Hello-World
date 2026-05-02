"""
Sammelt historische IPO-Listen (Nasdaq) und Kursdaten (Yahoo Finance).
"""

import requests
import yfinance as yf
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_historical_ipos(months_back: int = 6) -> list[dict]:
    """Holt gepreiste IPOs der letzten N Monate von der Nasdaq-API."""
    ipos = []
    seen = set()

    for i in range(months_back):
        month = (datetime.now() - relativedelta(months=i)).strftime("%Y-%m")
        try:
            resp = requests.get(
                "https://api.nasdaq.com/api/ipo/calendar",
                headers=HEADERS,
                params={"date": month},
                timeout=10,
            )
            resp.raise_for_status()
            data   = resp.json().get("data", {})
            priced = data.get("priced", {})
            # API liefert Rows direkt unter "priced", nicht in einer verschachtelten Tabelle
            rows = priced.get("rows") or priced.get("pricedTable", {}).get("rows", []) or []
            for row in rows:
                symbol = row.get("proposedTickerSymbol", "").strip()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                raw_date = row.get("pricedDate") or row.get("expectedPriceDate", "")
                ipos.append({
                    "symbol":   symbol,
                    "name":     row.get("companyName", "N/A"),
                    "date":     _parse_date(raw_date),
                    "exchange": row.get("proposedExchange", "N/A"),
                    "price":    row.get("proposedSharePrice", "N/A"),
                    "shares":   row.get("sharesOffered", "N/A"),
                })
        except Exception as e:
            print(f"  [Nasdaq {month}] Fehler: {e}")

    return [ipo for ipo in ipos if ipo["date"]]


def _parse_date(raw: str) -> str | None:
    """Wandelt M/D/YYYY oder YYYY-MM-DD in YYYY-MM-DD um."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
    return None


def fetch_first_day_prices(symbol: str, ipo_date_str: str) -> dict | None:
    """
    Holt Kursdaten vom ersten Handelstag eines IPOs via Yahoo Finance.
    Versucht bis zu 3 Handelstage nach dem IPO-Datum.
    Gibt open, price_5min, high, low, close zurück — oder None bei Misserfolg.
    """
    try:
        ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    days_ago = (date.today() - ipo_date).days

    # Intervall je nach Datenverfügbarkeit bei Yahoo Finance
    if days_ago <= 7:
        interval = "1m"
    elif days_ago <= 60:
        interval = "2m"
    else:
        interval = "1d"

    ticker = yf.Ticker(symbol)

    # Versuche bis zu 4 Tage nach IPO-Datum (Wochenenden / Feiertage)
    for offset in range(4):
        try_date = ipo_date + timedelta(days=offset)
        end_date = try_date + timedelta(days=1)

        try:
            hist = ticker.history(
                start=try_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )
        except Exception:
            continue

        if hist.empty:
            continue

        open_price = float(hist["Open"].iloc[0])

        if interval in ("1m", "2m"):
            # 5 Minuten ≈ 5 Bars bei 1m, ≈ 3 Bars bei 2m
            bars = 5 if interval == "1m" else 3
            idx = min(bars, len(hist) - 1)
            price_5min = float(hist["Close"].iloc[idx])
            is_intraday = True
        else:
            # Kein Intraday verfügbar → Tagesschluss als Näherung
            price_5min = float(hist["Close"].iloc[0])
            is_intraday = False

        return {
            "open":       open_price,
            "price_5min": price_5min,
            "high":       float(hist["High"].max()),
            "low":        float(hist["Low"].min()),
            "close":      float(hist["Close"].iloc[-1]),
            "interval":   interval,
            "is_intraday": is_intraday,
            "actual_date": str(try_date),
        }

    return None
