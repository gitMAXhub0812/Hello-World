"""
IPO Backtester
Strategie: Kauf bei Handelseröffnung, Verkauf nach 5 Minuten.
Keine echten Trades — nur historische Simulation.

Verwendung:
  python backtest.py                   → Basis-Backtest, letzte 6 Monate
  python backtest.py --filter          → Optimierte Strategie + Vergleich
  python backtest.py --months 12       → Längerer Zeitraum
  python backtest.py --size 500        → 500 € pro Trade
  python backtest.py --filter --months 12 --size 500
"""

import argparse
import json
import sys
from datetime import datetime
from data_collector import fetch_historical_ipos, fetch_first_day_prices

# ── Konfiguration ──────────────────────────────────────────────────────────────
DEFAULT_MONTHS   = 6
DEFAULT_SIZE_EUR = 1_000
SPREAD_PCT       = 0.003   # 0.3 % Spread (Kauf + Verkauf)
FEE_EUR          = 0.0     # Gebühr pro Trade

# Optimierte Filterregeln (aktiv mit --filter)
FILTER_MIN_PRICE  = 20.0   # kein SPAC-Müll, kein Mini-Cap
FILTER_MAX_PRICE  = 50.0   # über 50 zu risikoreich
FILTER_STOP_LOSS  = -5.0   # max. -5 % Verlust pro Trade
# ──────────────────────────────────────────────────────────────────────────────


def _is_spac(buy_price: float) -> bool:
    return 9.5 <= buy_price <= 10.5


def apply_filter(results: list) -> list:
    filtered = []
    for r in results:
        price = r["buy_price"]
        if price < FILTER_MIN_PRICE or price > FILTER_MAX_PRICE:
            continue
        r = dict(r)
        # Stop-Loss: Verlust auf -5 % begrenzen
        if r["pct"] < FILTER_STOP_LOSS:
            r["pct"]     = FILTER_STOP_LOSS
            r["net_pnl"] = (FILTER_STOP_LOSS / 100) * DEFAULT_SIZE_EUR
            r["won"]     = False
            r["sl_hit"]  = True
        else:
            r["sl_hit"]  = False
        filtered.append(r)
    return filtered


def simulate_trade(prices: dict, size: float) -> dict:
    buy_p      = prices["open"]  * (1 + SPREAD_PCT / 2)
    sell_p_eff = prices["price_5min"] * (1 - SPREAD_PCT / 2)
    shares     = size / buy_p
    net        = (sell_p_eff - buy_p) * shares - 2 * FEE_EUR
    pct        = (sell_p_eff - buy_p) / buy_p * 100
    return {
        "buy_price":  buy_p,
        "sell_price": sell_p_eff,
        "shares":     shares,
        "net_pnl":    net,
        "pct":        pct,
        "won":        net > 0,
        "sl_hit":     False,
    }


def _color(val: float, text: str) -> str:
    if val > 0:  return f"\033[92m{text}\033[0m"
    if val < 0:  return f"\033[91m{text}\033[0m"
    return text


def _calc_stats(results: list) -> dict:
    if not results:
        return {}
    won  = [r for r in results if r["won"]]
    lost = [r for r in results if not r["won"]]
    pnls = [r["net_pnl"] for r in results]

    cumulative, peak, max_dd = 0.0, 0.0, 0.0
    for r in results:
        cumulative += r["net_pnl"]
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)

    return {
        "total":       len(results),
        "won":         len(won),
        "lost":        len(lost),
        "hit_rate":    len(won) / len(results) * 100,
        "total_pnl":   sum(pnls),
        "avg_win_pct": sum(r["pct"] for r in won)  / len(won)  if won  else 0,
        "avg_los_pct": sum(r["pct"] for r in lost) / len(lost) if lost else 0,
        "avg_win_eur": sum(r["net_pnl"] for r in won)  / len(won)  if won  else 0,
        "avg_los_eur": sum(r["net_pnl"] for r in lost) / len(lost) if lost else 0,
        "best":        max(results, key=lambda r: r["pct"]),
        "worst":       min(results, key=lambda r: r["pct"]),
        "max_dd":      max_dd,
        "sl_hits":     sum(1 for r in results if r.get("sl_hit")),
    }


def _print_summary_block(label: str, s: dict, W: int) -> None:
    print(f"\n  [ {label} ]")
    print(f"  {'Trades':<24}: {s['total']:>6}")
    print(f"  {'Gewinnende Trades':<24}: {s['won']:>6}  ({s['hit_rate']:.1f} %)")
    print(f"  {'Verlierende Trades':<24}: {s['lost']:>6}  ({100-s['hit_rate']:.1f} %)")
    if s.get("sl_hits"):
        print(f"  {'davon Stop-Loss':<24}: {s['sl_hits']:>6}")
    aw = f"{s['avg_win_pct']:>+.2f} %  ({s['avg_win_eur']:>+.2f} EUR)"
    al = f"{s['avg_los_pct']:>+.2f} %  ({s['avg_los_eur']:>+.2f} EUR)"
    print(f"  {'Ø Gewinn':<24}: {_color(s['avg_win_pct'], aw)}")
    print(f"  {'Ø Verlust':<24}: {_color(s['avg_los_pct'], al)}")
    b = s["best"];  bs = f"{b['pct']:>+.2f} %  ({b['net_pnl']:>+.2f} EUR)"
    w = s["worst"]; ws = f"{w['pct']:>+.2f} %  ({w['net_pnl']:>+.2f} EUR)"
    print(f"  {'Bester Trade':<24}: {b['symbol']:<8} {_color(b['pct'], bs)}")
    print(f"  {'Schlechtester Trade':<24}: {w['symbol']:<8} {_color(w['pct'], ws)}")
    tp = f"{s['total_pnl']:>+.2f} EUR"
    dd = f"{-s['max_dd']:>+.2f} EUR"
    print(f"  {'Gesamtgewinn/-verlust':<24}: {_color(s['total_pnl'], tp)}")
    print(f"  {'Max. kum. Drawdown':<24}: {_color(-s['max_dd'], dd)}")


def _print_trade_table(results: list, W: int) -> None:
    print(f"\n{'='*W}")
    print(f"  EINZELNE TRADES")
    print(f"  {'Datum':<12} {'Ticker':<7} {'Name':<26} {'Kauf':>7} {'Verk.':>7} {'Rend.':>7}  {'G/V':>10}  SL  Src")
    print(f"  {'-'*(W-2)}")
    for r in sorted(results, key=lambda x: x["date"]):
        src    = "1m" if r.get("is_intraday") else "Tag"
        sl     = "SL" if r.get("sl_hit") else "  "
        ps     = f"{r['pct']:>+6.2f}%"
        ns     = f"{r['net_pnl']:>+9.2f} EUR"
        print(
            f"  {r['date']:<12} {r['symbol']:<7} {r['name'][:25]:<26} "
            f"{r['buy_price']:>7.2f} {r['sell_price']:>7.2f} "
            f"{_color(r['pct'], ps)}  {_color(r['net_pnl'], ns)}  {sl}  [{src}]"
        )
    print(f"{'='*W}\n")
    if any(not r.get("is_intraday") for r in results):
        print("  [Tag] = kein Intraday verfügbar, Tagesschlusskurs als Näherung.\n")


def _print_filter_rules() -> None:
    print(f"\n  FILTERREGELN (optimierte Strategie)")
    print(f"  {'Kein SPAC / Mini-Cap':<28}: Einstiegspreis >= {FILTER_MIN_PRICE:.0f} USD")
    print(f"  {'Kein Hochpreis-Risiko':<28}: Einstiegspreis <= {FILTER_MAX_PRICE:.0f} USD")
    print(f"  {'Stop-Loss':<28}: max. {FILTER_STOP_LOSS:.0f} % Verlust pro Trade")


def run_backtest(months: int, size: float, with_filter: bool) -> None:
    print(f"\nLade historische IPO-Daten ({months} Monate)...")
    ipos = fetch_historical_ipos(months)
    print(f"{len(ipos)} IPOs gefunden. Lade Kursdaten...\n")

    all_results, skipped = [], []
    for ipo in ipos:
        sys.stdout.write(f"  {ipo['symbol']:<8} {ipo['name'][:28]:<30} ... ")
        sys.stdout.flush()
        prices = fetch_first_day_prices(ipo["symbol"], ipo["date"])
        if not prices:
            print("keine Daten")
            skipped.append(ipo)
            continue
        trade = simulate_trade(prices, size)
        note  = "" if prices["is_intraday"] else " [Tag]"
        print(f"  {trade['pct']:+.2f} %{note}")
        all_results.append({**ipo, **prices, **trade})

    if not all_results:
        print("\nKeine auswertbaren Trades gefunden.")
        return

    W  = 80
    s_all = _calc_stats(all_results)

    print(f"\n{'='*W}")
    print(f"  IPO BACKTEST  |  Kauf bei Eröffnung, Verkauf nach 5 Min")
    print(f"  Zeitraum: letzte {months} Monate  |  Position: {size:,.0f} EUR  |  Spread: {SPREAD_PCT*100:.1f} %")
    print(f"{'='*W}")

    print(f"\n  PARAMETER")
    print(f"  {'Position pro Trade':<28}: {size:>8,.0f} EUR")
    print(f"  {'Spread-Schätzung':<28}: {SPREAD_PCT*100:>7.1f} %")
    print(f"  {'Gebühr pro Trade':<28}: {FEE_EUR:>8.2f} EUR")

    if with_filter:
        filtered    = apply_filter(all_results)
        s_filtered  = _calc_stats(filtered)

        _print_summary_block("OHNE Filter (alle IPOs)", s_all, W)
        _print_filter_rules()
        _print_summary_block("MIT Filter (optimierte Strategie)", s_filtered, W)

        delta_pnl = s_filtered["total_pnl"] - s_all["total_pnl"]
        delta_dd  = s_all["max_dd"] - s_filtered["max_dd"]
        print(f"\n  VERBESSERUNG durch Filter")
        print(f"  {'Weniger Trades':<28}: {s_all['total'] - s_filtered['total']:>+6}  (Fokus auf Qualität)")
        print(f"  {'Gewinn-Delta':<28}: {_color(delta_pnl, f'{delta_pnl:>+.2f} EUR')}")
        print(f"  {'Drawdown reduziert um':<28}: {_color(delta_dd, f'{delta_dd:>+.2f} EUR')}")
        print(f"  {'Trefferquote':<28}: {s_all['hit_rate']:.1f} %  ->  {s_filtered['hit_rate']:.1f} %")

        _print_trade_table(filtered, W)
        _save_results(filtered, "backtest_filtered.json")
    else:
        _print_summary_block("ALLE IPOs (kein Filter)", s_all, W)
        _print_trade_table(all_results, W)
        _save_results(all_results, "backtest_results.json")


def _save_results(results: list, path: str) -> None:
    export = [{k: v for k, v in r.items() if k != "won"} for r in results]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"run": datetime.now().isoformat(), "trades": export}, f, ensure_ascii=False, indent=2)
    print(f"  Ergebnisse gespeichert: {path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="IPO Backtester")
    parser.add_argument("--months", type=int,   default=DEFAULT_MONTHS,   help="Monate zurück (Standard: 6)")
    parser.add_argument("--size",   type=float, default=DEFAULT_SIZE_EUR, help="Position in EUR (Standard: 1000)")
    parser.add_argument("--filter", action="store_true",                  help="Optimierte Strategie + Vergleich anzeigen")
    args = parser.parse_args()
    run_backtest(args.months, args.size, args.filter)


if __name__ == "__main__":
    main()
