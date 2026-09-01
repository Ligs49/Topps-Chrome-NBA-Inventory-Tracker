"""
Hourly background monitor.

Recommended use:
- GitHub Actions runs this once per hour.
- It compares the latest status with inventory_state.json.
- It texts subscribers only when a retailer transitions into IN STOCK.

Important:
The public-page checkers are deliberately conservative and do not bypass
retailer anti-bot systems. Store-level APIs can be added later.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Import helper functions without Streamlit UI.
from inventory import STORES, RETAILERS, check_retailer, load_subscribers, _send_sms

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
    retailer_results = {name: check_retailer(name) for name in RETAILERS}

    alerts = []
    for store in STORES:
        key = f"{store['city']}|{store['store']}|{store['address']}"
        result = retailer_results[store["store"]]
        current[key] = {
            "status": result["status"],
            "price": result["price"],
            "checked_at": datetime.now(PACIFIC).isoformat(),
        }

        old_status = previous.get(key, {}).get("status")
        if result["status"] == "IN STOCK" and old_status != "IN STOCK":
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
        price = f"${result['price']:.2f}" if result["price"] is not None else "Price unavailable"
        body = (
            f"RESTOCK: Topps Chrome Updates Basketball\n"
            f"{store['store']} - {store['city']}\n"
            f"{store['address']}\n"
            f"{price}\n"
            f"Check retailer site before driving."
        )
        for phone in subscribers:
            ok, msg = _send_sms(phone, body)
            print(phone, ok, msg)

if __name__ == "__main__":
    main()
