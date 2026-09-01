import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from inventory import STORES, PRODUCTS, check_all_stores, load_subscribers, send_sms

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

def alert_numbers():
    # Production/background numbers should be kept in GitHub Secrets, not in a public repo.
    raw = os.getenv("ALERT_PHONE_NUMBERS", "")
    env_numbers = [x.strip() for x in raw.split(",") if x.strip()]
    if env_numbers:
        return env_numbers

    # Local subscribers.json remains useful for private/local testing.
    return load_subscribers()

def main():
    previous = load_state()
    check_time = datetime.now(PACIFIC).isoformat()

    results = check_all_stores()
    current = {}
    alerts = []

    for store, inventory in zip(STORES, results):
        key = f"{store['city']}|{store['store']}|{store['address']}"

        current[key] = {
            "status": inventory["status"],
            "price": inventory["price"],
            "signal": inventory["signal"],
            "source": inventory.get("source", ""),
            "checked_at": check_time,
        }

        old_status = previous.get(key, {}).get("status")

        # Only a verified LOCAL IN STOCK status can trigger a text.
        # ONLINE LISTING ONLY and CHECK MANUALLY never trigger alerts.
        if previous and inventory["status"] == "IN STOCK" and old_status != "IN STOCK":
            alerts.append((store, inventory))

    save_state(current)

    if not alerts:
        print("No verified new local restocks.")
        return

    numbers = alert_numbers()
    if not numbers:
        print("Verified restock detected, but no alert phone numbers are configured.")
        return

    for store, inventory in alerts:
        price = (
            f"${inventory['price']:.2f}"
            if isinstance(inventory.get("price"), (int, float))
            else "Price unavailable"
        )
        body = (
            "RESTOCK: Topps Chrome Updates Basketball\n"
            f"{store['store']} - {store['city']}\n"
            f"{store['address']}\n"
            f"{price}\n"
            "Verified local inventory signal. Recheck retailer before driving."
        )
        for number in numbers:
            ok, message = send_sms(number, body)
            print(number, ok, message)

if __name__ == "__main__":
    main()
