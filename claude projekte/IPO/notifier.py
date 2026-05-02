from win11toast import toast

NASDAQ_IPO_URL = "https://www.nasdaq.com/market-activity/ipos"


def send_desktop_notification(title: str, message: str, url: str = NASDAQ_IPO_URL) -> None:
    try:
        toast(
            title,
            message,
            on_click=url,
            app_id="IPO Tracker",
        )
    except Exception as e:
        print(f"[Desktop] {title}: {message}  (Fehler: {e})")


def notify_new_ipos(new_ipos: list[dict]) -> None:
    if not new_ipos:
        return

    names = ", ".join(ipo.get("name", "?") for ipo in new_ipos[:3])
    suffix = f" +{len(new_ipos) - 3} weitere" if len(new_ipos) > 3 else ""

    send_desktop_notification(
        title=f"IPO Tracker: {len(new_ipos)} neuer Börsengang!",
        message=f"{names}{suffix} — Klicken für Details",
    )
