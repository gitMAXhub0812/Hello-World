"""
Sammelt historische IPO-Listen (Nasdaq) und Kursdaten (Polygon.io, Fallback: Yahoo Finance).
"""

import os
import requests
import yfinance as yf
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── IPO-Liste ──────────────────────────────────────────────────────────────────

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
            rows   = priced.get("rows") or priced.get("pricedTable", {}).get("rows", []) or []
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
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
    return None


# ── Kursdaten: Polygon.io ──────────────────────────────────────────────────────

def fetch_polygon_bars(symbol: str, day: date) -> list[dict] | None:
    """
    Holt 1-Minuten-Bars für einen Tag von Polygon.io.
    Gibt eine Liste von {open, high, low, close, time} zurück oder None.
    """
    if not POLYGON_API_KEY:
        return None

    date_str = day.strftime("%Y-%m-%d")
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute"
        f"/{date_str}/{date_str}"
    )
    params = {
        "adjusted": "true",
        "sort":     "asc",
        "limit":    "50000",
        "apiKey":   POLYGON_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 403:
            return None  # Key ungültig oder Plan zu niedrig
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        return [
            {
                "open":  r["o"],
                "high":  r["h"],
                "low":   r["l"],
                "close": r["c"],
                "time":  datetime.fromtimestamp(r["t"] / 1000).strftime("%H:%M"),
            }
            for r in results
        ]
    except Exception:
        return None


def fetch_first_day_prices(symbol: str, ipo_date_str: str, hold_minutes: int = 10) -> dict | None:
    """
    Holt Kursdaten vom ersten Handelstag eines IPOs.
    Verwendet Polygon.io (1m, unbegrenzte Historie) mit Yahoo Finance als Fallback.
    """
    try:
        ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    # Bis zu 4 Tage probieren (Wochenenden, Feiertage)
    for offset in range(4):
        try_date = ipo_date + timedelta(days=offset)

        # ── Versuch 1: Polygon.io ──────────────────────────────────────────
        bars = fetch_polygon_bars(symbol, try_date)
        if bars:
            open_price = bars[0]["open"]
            idx        = min(hold_minutes - 1, len(bars) - 1)
            price_out  = bars[idx]["close"]
            return {
                "open":        open_price,
                "price_5min":  price_out,
                "high":        max(b["high"]  for b in bars),
                "low":         min(b["low"]   for b in bars),
                "close":       bars[-1]["close"],
                "interval":    "1m",
                "is_intraday": True,
                "source":      "Polygon",
                "actual_date": str(try_date),
                "bars":        bars,
            }

        # ── Versuch 2: Yahoo Finance (Fallback) ────────────────────────────
        days_ago = (date.today() - try_date).days
        if days_ago <= 7:
            interval = "1m"
        elif days_ago <= 60:
            interval = "2m"
        else:
            interval = "1d"

        try:
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(
                start=try_date.strftime("%Y-%m-%d"),
                end=(try_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )
        except Exception:
            hist = None

        if hist is not None and not hist.empty:
            open_price  = float(hist["Open"].iloc[0])
            is_intraday = interval in ("1m", "2m")
            if is_intraday:
                iv_min    = 1 if interval == "1m" else 2
                idx       = min(hold_minutes // iv_min - 1, len(hist) - 1)
                price_out = float(hist["Close"].iloc[idx])
            else:
                price_out = float(hist["Close"].iloc[0])

            return {
                "open":        open_price,
                "price_5min":  price_out,
                "high":        float(hist["High"].max()),
                "low":         float(hist["Low"].min()),
                "close":       float(hist["Close"].iloc[-1]),
                "interval":    interval,
                "is_intraday": is_intraday,
                "source":      "Yahoo",
                "actual_date": str(try_date),
                "bars":        [],
            }

    return None


# ── Intraday-Bars für Optimizer ────────────────────────────────────────────────

def fetch_intraday_bars_full(symbol: str, ipo_date_str: str) -> tuple[list, str] | tuple[None, None]:
    """
    Gibt alle 1-Minuten-Bars des ersten Handelstages zurück (für Optimierung).
    Polygon bevorzugt, Yahoo Finance als Fallback.
    """
    try:
        ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, None

    for offset in range(4):
        try_date = ipo_date + timedelta(days=offset)

        # Polygon
        bars = fetch_polygon_bars(symbol, try_date)
        if bars:
            return [{k: v for k, v in b.items() if k != "time"} for b in bars], "1m"

        # Yahoo Fallback
        days_ago = (date.today() - try_date).days
        interval = "1m" if days_ago <= 7 else "2m" if days_ago <= 60 else "1d"

        try:
            import warnings
            warnings.filterwarnings("ignore")
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(
                start=try_date.strftime("%Y-%m-%d"),
                end=(try_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )
        except Exception:
            continue

        if hist is not None and not hist.empty:
            bars = [
                {"open": float(r["Open"]), "high": float(r["High"]),
                 "low":  float(r["Low"]),  "close": float(r["Close"])}
                for _, r in hist.iterrows()
            ]
            return bars, interval

    return None, None
