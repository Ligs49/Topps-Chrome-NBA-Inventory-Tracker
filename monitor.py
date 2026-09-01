import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from inventory import (
    STORES,
    RETAILERS,
    _check_all_retailers_parallel,
    load_subscribers,
    _send_sms,
)

PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_FILE = Path(__file__).parent / "inventory_state.json"

def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def main():
    previous = load_state()
    current = {}
    retailer_results = _check_all_retailers_parallel()
    alerts = []

    check_time = datetime.now(PACIFIC).isoformat()

    for store in STORES:
        key = f"{store['city']}|{store['store']}|{store['address']}"
        result = retailer_results[store["store"]]

        current[key] = {
            "status": result["status"],
            "price": result["price"],
            "signal": result["signal"],
            "checked_at": check_time,
        }

        old_status = previous.get(key, {}).get("status")

        # Do not send an alert merely because this is the first-ever check.
        if (
            previous
            and result["status"] == "IN STOCK"
            and old_status != "IN STOCK"
        ):
            alerts.append((store, result))

    save_state(current)

    if not alerts:
        print("No new restocks.")
        return

    subscribers = load_subscribers()

    if not subscribers:
        print("Restock detected, but no SMS subscribers are saved.")
        return

    for store, result in alerts:
        price = (
            f"${result['price']:.2f}"
            if result["price"] is not None
            else "Price unavailable"
        )

        body = (
            "RESTOCK: Topps Chrome Updates Basketball\n"
            f"{store['store']} - {store['city']}\n"
            f"{store['address']}\n"
            f"{price}\n"
            "Check retailer site before driving."
        )

        for phone in subscribers:
            ok, msg = _send_sms(phone, body)
            print(phone, ok, msg)

if __name__ == "__main__":
    main()
