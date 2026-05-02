"""
IPO Tracker - Überwacht bevorstehende Börsengänge.
Verwendung: python main.py
"""

import sys
from datetime import datetime
from ipo_fetcher import fetch_ipos, load_stored_ipos, merge_and_save
from notifier import notify_new_ipos


def _ipo_line(ipo: dict) -> str:
    return (
        f"  {ipo.get('date', '?'):12} "
        f"{ipo.get('symbol', '?'):8} "
        f"{ipo.get('name', 'N/A')[:35]:35} "
        f"{ipo.get('exchange', ''):8} "
        f"Preis: {ipo.get('price', 'N/A')}"
    )


def print_ipos(ipos: list[dict], title: str) -> None:
    print(f"\n{'='*80}")
    print(f"  {title}  |  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*80}")
    if not ipos:
        print("  Keine Einträge gefunden.")
    else:
        print(f"  {'Datum':12} {'Ticker':8} {'Name':35} {'Börse':8} Preis")
        print(f"  {'-'*76}")
        for ipo in sorted(ipos, key=lambda x: x.get("date", "")):
            print(_ipo_line(ipo))
    print(f"{'='*80}\n")


def check_now() -> None:
    print("Suche nach neuen IPOs...")
    try:
        fetched  = fetch_ipos()
        new_ipos = merge_and_save(fetched)

        if new_ipos:
            print(f"\n{len(new_ipos)} neuer Börsengang gefunden!")
            print_ipos(new_ipos, "Neue IPOs")
            notify_new_ipos(new_ipos)
        else:
            print("Keine neuen IPOs seit der letzten Prüfung.")
            print(f"Gesamt bekannte IPOs: {len(load_stored_ipos())}")
    except ValueError as e:
        print(f"\nKonfigurationsfehler: {e}")
    except Exception as e:
        print(f"\nFehler beim Abrufen: {e}")


def show_all() -> None:
    ipos = load_stored_ipos()
    print_ipos(ipos, f"Alle gespeicherten IPOs ({len(ipos)})")


def show_upcoming() -> None:
    today = datetime.today().strftime("%Y-%m-%d")
    ipos  = [i for i in load_stored_ipos() if i.get("date", "") >= today]
    print_ipos(ipos, f"Bevorstehende IPOs ({len(ipos)})")


def show_menu() -> None:
    print("\n--- IPO TRACKER ---")
    print("1  Jetzt nach neuen IPOs suchen")
    print("2  Alle gespeicherten IPOs anzeigen")
    print("3  Nur bevorstehende IPOs anzeigen")
    print("0  Beenden")
    print("-------------------")


def main() -> None:
    # Headless-Modus: python main.py --check (für cron / Task Scheduler)
    if "--check" in sys.argv:
        check_now()
        return

    while True:
        show_menu()
        choice = input("Auswahl: ").strip()
        if choice == "1":
            check_now()
        elif choice == "2":
            show_all()
        elif choice == "3":
            show_upcoming()
        elif choice == "0":
            print("Tschüss!")
            break
        else:
            print("Ungültige Eingabe.")


if __name__ == "__main__":
    main()
