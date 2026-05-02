"""
IPO Backtester
Strategie: Kauf bei Handelseröffnung, Verkauf nach 5 Minuten.
Keine echten Trades — nur historische Simulation.

Verwendung:
  python backtest.py              → letzte 6 Monate, 1.000 € pro Trade
  python backtest.py --months 12  → letzte 12 Monate
  python backtest.py --size 500   → 500 € pro Trade
"""

import argparse
import json
import sys
from datetime import datetime
from data_collector import fetch_historical_ipos, fetch_first_day_prices

# ── Konfiguration ──────────────────────────────────────────────────────────────
DEFAULT_MONTHS    = 6
DEFAULT_SIZE_EUR  = 1_000   # € pro Trade
SPREAD_PCT        = 0.003   # 0.3 % Spread-Schätzung (Kauf + Verkauf zusammen)
FEE_EUR           = 0.0     # Gebühr pro Trade in € (0 = Neobroker wie Trade Republic)
# ──────────────────────────────────────────────────────────────────────────────


def simulate_trade(prices: dict, size: float) -> dict:
    open_p = prices["open"]
    sell_p = prices["price_5min"]

    # Halber Spread beim Kauf (teurer), halber beim Verkauf (billiger)
    buy_p  = open_p * (1 + SPREAD_PCT / 2)
    sell_p_eff = sell_p * (1 - SPREAD_PCT / 2)

    shares   = size / buy_p
    gross    = (sell_p_eff - buy_p) * shares
    net      = gross - 2 * FEE_EUR
    pct      = (sell_p_eff - buy_p) / buy_p * 100

    return {
        "buy_price":  buy_p,
        "sell_price": sell_p_eff,
        "shares":     shares,
        "gross_pnl":  gross,
        "net_pnl":    net,
        "pct":        pct,
        "won":        net > 0,
    }


def _color(val: float, text: str) -> str:
    if val > 0:
        return f"\033[92m{text}\033[0m"   # grün
    if val < 0:
        return f"\033[91m{text}\033[0m"   # rot
    return text


def run_backtest(months: int, size: float) -> None:
    print(f"\nLade historische IPO-Daten ({months} Monate)...")
    ipos = fetch_historical_ipos(months)
    print(f"{len(ipos)} IPOs gefunden. Lade Kursdaten...\n")

    results = []
    skipped = []

    for ipo in ipos:
        sym  = ipo["symbol"]
        name = ipo["name"][:28]
        sys.stdout.write(f"  {sym:<8} {name:<30} ... ")
        sys.stdout.flush()

        prices = fetch_first_day_prices(sym, ipo["date"])
        if not prices:
            print("keine Daten")
            skipped.append(ipo)
            continue

        trade = simulate_trade(prices, size)
        note  = "" if prices["is_intraday"] else " [Tageskurs]"
        print(f"  {trade['pct']:+.2f} %{note}")

        results.append({**ipo, **prices, **trade})

    if not results:
        print("\nKeine auswertbaren Trades gefunden.")
        return

    _print_report(results, skipped, months, size)
    _save_results(results)


def _print_report(results: list, skipped: list, months: int, size: float) -> None:
    won   = [r for r in results if r["won"]]
    lost  = [r for r in results if not r["won"]]
    total = len(results)

    total_pnl   = sum(r["net_pnl"] for r in results)
    avg_win_pct = sum(r["pct"] for r in won)  / len(won)  if won  else 0
    avg_los_pct = sum(r["pct"] for r in lost) / len(lost) if lost else 0
    avg_win_eur = sum(r["net_pnl"] for r in won)  / len(won)  if won  else 0
    avg_los_eur = sum(r["net_pnl"] for r in lost) / len(lost) if lost else 0

    best  = max(results, key=lambda r: r["pct"])
    worst = min(results, key=lambda r: r["pct"])

    # Maximaler kumulierter Drawdown
    cumulative = 0.0
    peak       = 0.0
    max_dd     = 0.0
    for r in results:
        cumulative += r["net_pnl"]
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    W = 76
    print(f"\n{'='*W}")
    print(f"  IPO BACKTEST  |  Strategie: Kauf bei Eröffnung, Verkauf nach 5 Min")
    print(f"  Zeitraum: letzte {months} Monate  |  Analysierte IPOs: {total}  |  Übersprungen: {len(skipped)}")
    print(f"{'='*W}")

    print(f"\n  PARAMETER")
    print(f"  {'Position pro Trade':<22}: {size:>10,.0f} €")
    print(f"  {'Spread-Schätzung':<22}: {SPREAD_PCT*100:>9.1f} %  (Kauf + Verkauf)")
    print(f"  {'Gebühr pro Trade':<22}: {FEE_EUR:>10.2f} €")

    print(f"\n  ERGEBNISSE")
    print(f"  {'Trades gesamt':<22}: {total:>10}")
    hit = len(won) / total * 100
    print(f"  {'Gewinnende Trades':<22}: {len(won):>10}  ({hit:.1f} %)")
    print(f"  {'Verlierende Trades':<22}: {len(lost):>10}  ({100-hit:.1f} %)")

    print(f"\n  {'Ø Gewinn':<22}: {_color(avg_win_pct, f'{avg_win_pct:>+9.2f} %  ({avg_win_eur:>+.2f} €)')}")
    print(f"  {'Ø Verlust':<22}: {_color(avg_los_pct, f'{avg_los_pct:>+9.2f} %  ({avg_los_eur:>+.2f} €)')}")

    best_str  = f"{best['pct']:>+.2f} %  ({best['net_pnl']:>+.2f} €)"
    worst_str = f"{worst['pct']:>+.2f} %  ({worst['net_pnl']:>+.2f} €)"
    print(f"\n  {'Bester Trade':<22}: {best['symbol']:<8} {_color(best['pct'], best_str)}")
    print(f"  {'Schlechtester Trade':<22}: {worst['symbol']:<8} {_color(worst['pct'], worst_str)}")

    print(f"\n  {'Gesamtgewinn/-verlust':<22}: {_color(total_pnl, f'{total_pnl:>+10.2f} €')}")
    print(f"  {'Max. kum. Drawdown':<22}: {_color(-max_dd, f'{-max_dd:>+10.2f} €')}")

    print(f"\n{'='*W}")
    print(f"  EINZELNE TRADES")
    print(f"  {'Datum':<12} {'Ticker':<8} {'Name':<28} {'Kauf':>7} {'Verk.':>7} {'Rend.':>7}  {'G/V (€)':>9}  Quelle")
    print(f"  {'-'*(W-2)}")

    for r in sorted(results, key=lambda x: x["date"]):
        src  = "1m" if r.get("is_intraday") else "Tag"
        pct_str = f"{r['pct']:>+6.2f}%"
        pnl_str = f"{r['net_pnl']:>+9.2f} EUR"
        line = (
            f"  {r['date']:<12} {r['symbol']:<8} {r['name'][:27]:<28} "
            f"{r['buy_price']:>7.2f} {r['sell_price']:>7.2f} "
            f"{_color(r['pct'], pct_str)}  "
            f"{_color(r['net_pnl'], pnl_str)}  [{src}]"
        )
        print(line)

    print(f"{'='*W}\n")

    if any(not r["is_intraday"] for r in results):
        print("  Hinweis: [Tag] = kein Intraday verfügbar, Tagesschlusskurs als Näherung.\n")


def _save_results(results: list) -> None:
    path = "backtest_results.json"
    export = [
        {k: v for k, v in r.items() if k not in ("won",)}
        for r in results
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"run": datetime.now().isoformat(), "trades": export}, f, ensure_ascii=False, indent=2)
    print(f"  Ergebnisse gespeichert: {path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="IPO Backtester")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS, help="Wie viele Monate zurück (Standard: 6)")
    parser.add_argument("--size",   type=float, default=DEFAULT_SIZE_EUR, help="Positionsgröße in € (Standard: 1000)")
    args = parser.parse_args()

    run_backtest(args.months, args.size)


if __name__ == "__main__":
    main()
