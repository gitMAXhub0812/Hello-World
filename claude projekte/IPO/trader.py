"""
IPO Trader — Semi-automatisch via Interactive Brokers (IBKR)
============================================================
Kein Trade ohne deine Bestätigung. Der Code überwacht, du entscheidest.

Voraussetzungen:
  1. IBKR TWS läuft im Hintergrund (Einstellungen → API → Socket aktivieren)
  2. pip install ib_insync
  3. Paper Trading zum Testen: Port 7497
     Live Trading:             Port 7496

Verwendung:
  python trader.py                    → überwacht heutige IPOs
  python trader.py --paper            → Paper Trading (Testmodus, kein echtes Geld)
  python trader.py --symbol ARXS      → nur diesen Ticker überwachen
"""

import argparse
import time
import sys
import threading
from datetime import datetime, timedelta
from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, util
from data_collector import fetch_historical_ipos
from notifier import send_desktop_notification

# ── Konfiguration ──────────────────────────────────────────────────────────────
POSITION_EUR    = 400      # € pro Trade
STOP_LOSS_PCT   = 0.05     # 5 % Stop-Loss
HOLD_MINUTES    = 10       # Haltedauer in Minuten
FILTER_MIN      = 20.0     # Mindestpreis IPO-Aktie
FILTER_MAX      = 50.0     # Höchstpreis IPO-Aktie
EUR_USD_RATE    = 1.08     # Näherungswert EUR→USD (wird bei Orderplatzierung abgefragt)
TWS_HOST        = "127.0.0.1"
TWS_PORT_LIVE   = 7496
TWS_PORT_PAPER  = 7497
# ──────────────────────────────────────────────────────────────────────────────


def connect(paper: bool) -> IB:
    ib   = IB()
    port = TWS_PORT_PAPER if paper else TWS_PORT_LIVE
    mode = "PAPER TRADING" if paper else "LIVE TRADING"
    print(f"\n[{_now()}] Verbinde mit IBKR TWS ({mode}, Port {port})...")
    try:
        ib.connect(TWS_HOST, port, clientId=42, timeout=10)
        print(f"[{_now()}] Verbunden. Konto: {ib.managedAccounts()}")
        return ib
    except Exception as e:
        print(f"\nFEHLER: Keine Verbindung zu TWS.\n"
              f"Bitte TWS starten und API aktivieren (Einstellungen → API → Socket).\n"
              f"Details: {e}")
        sys.exit(1)


def get_todays_ipos() -> list[dict]:
    """Gibt IPOs zurück, die heute oder gestern gepreist wurden."""
    today     = datetime.today().strftime("%Y-%m-%d")
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    all_ipos  = fetch_historical_ipos(months_back=1)
    return [
        ipo for ipo in all_ipos
        if ipo.get("date") in (today, yesterday)
    ]


def get_usd_rate(ib: IB) -> float:
    """Holt aktuellen EUR/USD-Kurs von IBKR."""
    try:
        from ib_insync import Forex
        contract = Forex("EURUSD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(1)
        rate = ticker.last or ticker.bid or EUR_USD_RATE
        ib.cancelMktData(contract)
        return float(rate)
    except Exception:
        return EUR_USD_RATE


def monitor_ipo(ib: IB, symbol: str, name: str, paper: bool) -> None:
    """
    Überwacht einen IPO-Ticker auf den ersten Trade.
    Fragt nach Bestätigung und platziert dann den Trade.
    """
    print(f"\n[{_now()}] Überwache {symbol} ({name})...")

    contract = Stock(symbol, "SMART", "USD")
    try:
        ib.qualifyContracts(contract)
    except Exception as e:
        print(f"[{_now()}] {symbol}: Nicht bei IBKR verfügbar — {e}")
        return

    ticker = ib.reqMktData(contract, "", False, False)
    last_price = None

    while True:
        ib.sleep(1)
        current = ticker.last or ticker.bid or ticker.ask

        if not current or current <= 0:
            continue

        # Erster Trade erkannt
        if last_price is None:
            last_price = current
            _on_first_trade(ib, contract, ticker, symbol, name, current, paper)
            return

        last_price = current


def _on_first_trade(ib, contract, ticker, symbol, name, open_price, paper):
    """Wird aufgerufen sobald der erste Trade erkannt wurde."""
    mode_tag = " [PAPER]" if paper else ""
    print(f"\n{'='*60}")
    print(f"  IPO STARTET{mode_tag}: {symbol} — {name}")
    print(f"  Eröffnungskurs  : ${open_price:.2f}")
    print(f"  Zeit            : {_now()}")
    print(f"{'='*60}")

    # Preisfilter prüfen
    if not (FILTER_MIN <= open_price <= FILTER_MAX):
        msg = f"{symbol} ausserhalb Preisfilter (${open_price:.2f}, Filter: ${FILTER_MIN:.0f}–${FILTER_MAX:.0f})"
        print(f"  → KEIN TRADE: {msg}")
        send_desktop_notification(f"IPO: {symbol}", f"Kein Trade — {msg}")
        return

    # EUR/USD holen und Stückzahl berechnen
    eur_usd    = get_usd_rate(ib)
    budget_usd = POSITION_EUR * eur_usd
    quantity   = max(1, int(budget_usd / open_price))
    cost_usd   = quantity * open_price
    cost_eur   = cost_usd / eur_usd
    stop_price = round(open_price * (1 - STOP_LOSS_PCT), 2)

    print(f"\n  VORGESCHLAGENER TRADE:")
    print(f"  Aktien          : {quantity} Stück")
    print(f"  Kaufkurs ~      : ${open_price:.2f}")
    print(f"  Gesamtkosten    : ${cost_usd:.2f}  (~{cost_eur:.0f} EUR)")
    print(f"  Stop-Loss       : ${stop_price:.2f}  (-{STOP_LOSS_PCT*100:.0f} %)")
    print(f"  Geplanter Verk. : in {HOLD_MINUTES} Minuten")
    print(f"  Modus           : {'PAPER (kein echtes Geld)' if paper else '*** LIVE — ECHTES GELD ***'}")

    # Desktop-Benachrichtigung
    send_desktop_notification(
        f"IPO: {symbol} bei ${open_price:.2f}",
        f"{quantity} Aktien für ~{cost_eur:.0f} EUR — Terminal öffnen um zu bestätigen!"
    )

    # Bestätigung im Terminal
    print(f"\n  → Kaufen? [j/n]: ", end="", flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer != "j":
        print(f"  → Trade abgebrochen.")
        return

    _place_trade(ib, contract, symbol, quantity, open_price, stop_price, paper)


def _place_trade(ib, contract, symbol, quantity, open_price, stop_price, paper):
    """Platziert Kauf, Stop-Loss und plant den Verkauf nach HOLD_MINUTES."""
    print(f"\n[{_now()}] Platziere Kauforder: {quantity}x {symbol}...")

    buy_order   = MarketOrder("BUY", quantity)
    trade       = ib.placeOrder(contract, buy_order)
    ib.sleep(2)

    filled_price = trade.orderStatus.avgFillPrice or open_price
    print(f"[{_now()}] Kauf ausgeführt bei ${filled_price:.2f}")

    # Stop-Loss setzen
    sl_order = StopOrder("SELL", quantity, stop_price, outsideRth=False)
    ib.placeOrder(contract, sl_order)
    print(f"[{_now()}] Stop-Loss gesetzt bei ${stop_price:.2f}")

    sell_time = datetime.now() + timedelta(minutes=HOLD_MINUTES)
    print(f"[{_now()}] Automatischer Verkauf um {sell_time.strftime('%H:%M:%S')} Uhr")

    # Timer für Verkauf
    def sell_after_hold():
        remaining = (sell_time - datetime.now()).total_seconds()
        if remaining > 0:
            time.sleep(remaining)

        print(f"\n[{_now()}] {HOLD_MINUTES} Minuten erreicht — Verkaufe {quantity}x {symbol}...")
        ib.cancelOrder(sl_order)
        ib.sleep(0.5)

        sell_order = MarketOrder("SELL", quantity)
        sell_trade = ib.placeOrder(contract, sell_order)
        ib.sleep(2)

        sell_price = sell_trade.orderStatus.avgFillPrice or 0
        if sell_price:
            pnl_usd = (sell_price - filled_price) * quantity
            pnl_pct = (sell_price - filled_price) / filled_price * 100
            result  = "GEWINN" if pnl_usd > 0 else "VERLUST"
            print(f"\n{'='*60}")
            print(f"  TRADE ABGESCHLOSSEN — {result}")
            print(f"  Kauf            : ${filled_price:.2f}")
            print(f"  Verkauf         : ${sell_price:.2f}")
            print(f"  Rendite         : {pnl_pct:+.2f} %")
            print(f"  G/V             : ${pnl_usd:+.2f}")
            print(f"{'='*60}\n")
            send_desktop_notification(
                f"{symbol}: Trade abgeschlossen",
                f"{pnl_pct:+.2f} % | ${pnl_usd:+.2f}"
            )

    threading.Thread(target=sell_after_hold, daemon=True).start()


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="IPO Trader via IBKR")
    parser.add_argument("--paper",  action="store_true", help="Paper Trading (kein echtes Geld)")
    parser.add_argument("--symbol", type=str, default="",  help="Nur diesen Ticker überwachen")
    args = parser.parse_args()

    if not args.paper:
        print("\n" + "!"*60)
        print("  ACHTUNG: LIVE-MODUS — echtes Geld wird eingesetzt!")
        print("  Zum Testen: python trader.py --paper")
        print("!"*60)
        antwort = input("  Fortfahren im Live-Modus? [j/n]: ").strip().lower()
        if antwort != "j":
            print("  Abgebrochen. Starte mit --paper zum Testen.")
            sys.exit(0)

    ib = connect(args.paper)

    if args.symbol:
        ipos = [{"symbol": args.symbol, "name": args.symbol, "date": datetime.today().strftime("%Y-%m-%d")}]
    else:
        ipos = get_todays_ipos()
        if not ipos:
            print(f"[{_now()}] Keine IPOs für heute gefunden.")
            print(f"          Verwende --symbol TICKER um manuell einen Ticker anzugeben.")
            ib.disconnect()
            return

    print(f"\n[{_now()}] Überwache {len(ipos)} IPO(s):")
    for ipo in ipos:
        print(f"  → {ipo['symbol']} ({ipo['name']})")

    # Alle IPOs parallel überwachen
    threads = []
    for ipo in ipos:
        t = threading.Thread(
            target=monitor_ipo,
            args=(ib, ipo["symbol"], ipo["name"], args.paper),
            daemon=True,
        )
        t.start()
        threads.append(t)

    print(f"\n[{_now()}] Warte auf ersten Trade... (Strg+C zum Beenden)\n")
    try:
        while any(t.is_alive() for t in threads):
            ib.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] Beendet.")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    util.logToConsole(None)  # IBKR-Logs unterdrücken
    main()
