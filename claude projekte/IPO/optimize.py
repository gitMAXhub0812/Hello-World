"""
Haltedauer-Optimierung für die IPO-Strategie.
Testet alle Haltedauern von 1 Min bis Tagesende und findet das Optimum.

Verwendung:
  python optimize.py              → letzte 6 Monate
  python optimize.py --months 12
"""

import argparse
import json
import sys
import warnings
from datetime import datetime
from data_collector import fetch_historical_ipos, fetch_intraday_bars_full

warnings.filterwarnings("ignore")

# ── Konfiguration ──────────────────────────────────────────────────────────────
HOLD_PERIODS    = [1, 2, 3, 5, 7, 10, 15, 20, 30, 60, 120, "EOD"]
SPREAD_PCT      = 0.003
FILTER_MIN      = 20.0
FILTER_MAX      = 50.0
STOP_LOSS_PCT   = -5.0
POSITION_EUR    = 1_000
# ──────────────────────────────────────────────────────────────────────────────


def fetch_intraday_bars(symbol: str, ipo_date_str: str) -> tuple[list, str] | tuple[None, None]:
    """
    Gibt (bars_as_list, interval) zurück, wobei bars eine Liste von
    {"open", "high", "low", "close"} Dicts ist — oder (None, None) bei Misserfolg.
    """
    try:
        ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, None

    days_ago = (date.today() - ipo_date).days

    if days_ago <= 7:
        interval = "1m"
    elif days_ago <= 60:
        interval = "2m"
    else:
        interval = "1d"

    ticker = yf.Ticker(symbol)

    for offset in range(4):
        try_date = ipo_date + timedelta(days=offset)
        try:
            hist = ticker.history(
                start=try_date.strftime("%Y-%m-%d"),
                end=(try_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )
        except Exception:
            continue

        if hist.empty:
            continue

        bars = [
            {
                "open":  float(row["Open"]),
                "high":  float(row["High"]),
                "low":   float(row["Low"]),
                "close": float(row["Close"]),
            }
            for _, row in hist.iterrows()
        ]
        return bars, interval

    return None, None


def simulate_hold(bars: list, hold: int | str, interval_min: int) -> float | None:
    """
    Simuliert einen Trade: Kauf am Eröffnungskurs des ersten Balkens,
    Verkauf nach `hold` Minuten (oder am Tagesende bei 'EOD').
    Gibt die prozentuale Rendite zurück (nach Spread, mit Stop-Loss).
    """
    if not bars:
        return None

    buy_p = bars[0]["open"] * (1 + SPREAD_PCT / 2)

    if hold == "EOD":
        sell_bar = bars[-1]
    else:
        idx      = max(0, min(hold // interval_min - 1, len(bars) - 1))
        sell_bar = bars[idx]

    sell_p = sell_bar["close"] * (1 - SPREAD_PCT / 2)

    # Intrabar Stop-Loss: prüfe ob Low den SL berührt hat
    touched_sl = False
    check_bars = bars[:idx + 1] if hold != "EOD" else bars
    for b in check_bars:
        if (b["low"] - buy_p) / buy_p * 100 <= STOP_LOSS_PCT:
            touched_sl = True
            break

    if touched_sl:
        return STOP_LOSS_PCT

    return (sell_p - buy_p) / buy_p * 100


def _interval_minutes(interval: str) -> int:
    return {"1m": 1, "2m": 2, "1d": 390}.get(interval, 1)


def _color(val: float, text: str) -> str:
    if val > 0:  return f"\033[92m{text}\033[0m"
    if val < 0:  return f"\033[91m{text}\033[0m"
    return text


def run_optimization(months: int) -> None:
    print(f"\nLade historische IPO-Daten ({months} Monate)...")
    all_ipos = fetch_historical_ipos(months)

    # Nur gefilterte IPOs ($20–$50)
    ipos = [
        ipo for ipo in all_ipos
        if ipo.get("date")
    ]
    print(f"{len(all_ipos)} IPOs gesamt, lade Intraday-Daten...\n")

    # Für jeden IPO: Intraday-Bars laden
    trade_data = []
    skipped    = 0

    for ipo in ipos:
        sym = ipo["symbol"]
        sys.stdout.write(f"  {sym:<8} {ipo['name'][:30]:<32} ... ")
        sys.stdout.flush()

        bars, interval = fetch_intraday_bars_full(sym, ipo["date"])
        if not bars:
            print("keine Daten")
            skipped += 1
            continue

        open_price = bars[0]["open"] * (1 + SPREAD_PCT / 2)

        # Preisfilter erst nach Datenabruf (echter Handelspreis)
        if not (FILTER_MIN <= open_price <= FILTER_MAX):
            print(f"gefiltert ({open_price:.2f} USD)")
            continue

        print(f"OK  ({len(bars)} Balken, {interval})")
        trade_data.append({"ipo": ipo, "bars": bars, "interval": interval, "open": open_price})

    if not trade_data:
        print("\nKeine auswertbaren Trades gefunden.")
        return

    print(f"\n{len(trade_data)} IPOs analysiert, {skipped} ohne Daten.\n")

    # Für jede Haltedauer: alle Trades simulieren
    results = {}   # hold -> [pct, ...]

    for entry in trade_data:
        bars     = entry["bars"]
        interval = entry["interval"]
        iv_min   = _interval_minutes(interval)

        for hold in HOLD_PERIODS:
            # Haltedauer kürzer als Balken-Intervall: überspringen
            if hold != "EOD" and hold < iv_min:
                continue

            pct = simulate_hold(bars, hold, iv_min)
            if pct is None:
                continue

            results.setdefault(hold, []).append(pct)

    # Auswertung
    _print_report(results, trade_data, months)
    _save(results, trade_data)


def _stats(pcts: list[float]) -> dict:
    if not pcts:
        return {}
    won      = [p for p in pcts if p > 0]
    lost     = [p for p in pcts if p <= 0]
    total    = sum(p * POSITION_EUR / 100 for p in pcts)
    hit_rate = len(won) / len(pcts) * 100
    avg      = sum(pcts) / len(pcts)
    sl_hits  = sum(1 for p in pcts if p == STOP_LOSS_PCT)

    # max kumulierter Drawdown
    cum, peak, dd = 0.0, 0.0, 0.0
    for p in pcts:
        cum  += p * POSITION_EUR / 100
        peak  = max(peak, cum)
        dd    = max(dd, peak - cum)

    return {
        "n":        len(pcts),
        "hit_rate": hit_rate,
        "avg_pct":  avg,
        "total_eur": total,
        "max_dd":   dd,
        "sl_hits":  sl_hits,
        "avg_win":  sum(won)  / len(won)  if won  else 0,
        "avg_los":  sum(lost) / len(lost) if lost else 0,
    }


def _hold_label(hold) -> str:
    if hold == "EOD": return "Tagesende"
    if hold >= 60:    return f"{hold//60}h {hold%60:02d}m" if hold % 60 else f"{hold//60}h"
    return f"{hold} Min"


def _print_report(results: dict, trade_data: list, months: int) -> None:
    W = 84
    print(f"\n{'='*W}")
    print(f"  HALTEDAUER-OPTIMIERUNG  |  Strategie: Kauf bei Eröffnung, Verkauf nach X")
    print(f"  Zeitraum: letzte {months} Monate  |  Filter: {FILTER_MIN:.0f}–{FILTER_MAX:.0f} USD  |  Stop-Loss: {STOP_LOSS_PCT:.0f} %")
    print(f"{'='*W}")
    print(f"\n  {'Haltedauer':<12} {'Trades':>7} {'Treffer':>8} {'Ø Rend.':>9} {'Gesamt':>11} {'Max-DD':>10} {'SL-Hits':>8}")
    print(f"  {'-'*(W-2)}")

    stats_list = []
    for hold in HOLD_PERIODS:
        if hold not in results or not results[hold]:
            continue
        s = _stats(results[hold])
        s["hold"] = hold
        stats_list.append(s)

    # Sortierung: nach Gesamt-EUR anzeigen, aber Optimum markieren
    best_pnl = max(stats_list, key=lambda s: s["total_eur"])
    best_hit = max(stats_list, key=lambda s: s["hit_rate"])
    best_dd  = min(stats_list, key=lambda s: s["max_dd"])

    for s in stats_list:
        label   = _hold_label(s["hold"])
        markers = []
        if s["hold"] == best_pnl["hold"]: markers.append("MAX GEWINN")
        if s["hold"] == best_hit["hold"]: markers.append("MAX TREFFER")
        if s["hold"] == best_dd["hold"]:  markers.append("MIN DRAWDOWN")
        tag     = f"  << {', '.join(markers)}" if markers else ""

        t_str = f"{s['total_eur']:>+.0f} EUR"
        d_str = f"{-s['max_dd']:>+.0f} EUR"
        a_str = f"{s['avg_pct']:>+.2f} %"

        line = (
            f"  {label:<12} {s['n']:>7} {s['hit_rate']:>7.1f} % "
            f"{_color(s['avg_pct'], a_str):>9} "
            f"{_color(s['total_eur'], t_str):>11} "
            f"{_color(-s['max_dd'], d_str):>10} "
            f"{s['sl_hits']:>8}"
        )
        print(line + tag)

    print(f"\n{'='*W}")

    # Detail-Empfehlung
    opt     = best_pnl
    avg_str = f"{opt['avg_pct']:+.2f} %"
    aw_str  = f"{opt['avg_win']:+.2f} %"
    al_str  = f"{opt['avg_los']:+.2f} %"
    tp_str  = f"{opt['total_eur']:+.2f} EUR"
    dd_str  = f"{-opt['max_dd']:+.2f} EUR"
    print(f"\n  EMPFEHLUNG: Haltedauer {_hold_label(opt['hold'])}")
    print(f"  Trefferquote  : {opt['hit_rate']:.1f} %")
    print(f"  Avg Rendite   : {_color(opt['avg_pct'], avg_str)}")
    print(f"  Avg Gewinn    : {_color(opt['avg_win'], aw_str)}   Avg Verlust: {_color(opt['avg_los'], al_str)}")
    print(f"  Gesamtgewinn  : {_color(opt['total_eur'], tp_str)}")
    print(f"  Max. Drawdown : {_color(-opt['max_dd'], dd_str)}")
    print(f"  Stop-Loss-Hits: {opt['sl_hits']}")
    print(f"\n  Hinweis: Analyse basiert auf {len(trade_data)} IPOs mit verfuegbaren Intraday-Daten.")
    print(f"  Aeltere IPOs (nur Tageskurs) sind in der Analyse nicht enthalten.\n")


def _save(results: dict, trade_data: list) -> None:
    export = {
        "run": datetime.now().isoformat(),
        "config": {
            "filter_min": FILTER_MIN,
            "filter_max": FILTER_MAX,
            "stop_loss_pct": STOP_LOSS_PCT,
            "position_eur": POSITION_EUR,
            "spread_pct": SPREAD_PCT,
        },
        "hold_periods": {
            str(h): _stats(results[h]) for h in HOLD_PERIODS if h in results
        },
        "trades_analyzed": len(trade_data),
    }
    with open("optimize_results.json", "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print("  Ergebnisse gespeichert: optimize_results.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Haltedauer-Optimierung")
    parser.add_argument("--months", type=int, default=6, help="Monate zurueck (Standard: 6)")
    args = parser.parse_args()
    run_optimization(args.months)


if __name__ == "__main__":
    main()
