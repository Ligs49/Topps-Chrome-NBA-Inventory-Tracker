import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from inventory import STORES, RETAILERS, load_subscribers, save_subscriber, send_test_sms

PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_FILE = Path(__file__).parent / "inventory_state.json"

st.set_page_config(
    page_title="Topps 2026 Chrome NBA Inventory Tracker",
    page_icon="🏀",
    layout="wide",
)

# Refresh the DISPLAY every 5 minutes.
# This does NOT perform a retailer inventory check.
st_autorefresh(interval=300_000, key="display_refresh")

st.title("🏀 Topps 2026 Chrome NBA Inventory Tracker")
st.caption("Davis & Woodland, California • Big 5 • Target • Walmart • Best Buy • CVS")

st.info(
    "Inventory is checked automatically by GitHub once per hour. "
    "Reloading this page does not trigger another inventory check."
)

def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

state = load_state()

rows = []
latest_check = None

for store in STORES:
    key = f"{store['city']}|{store['store']}|{store['address']}"
    saved = state.get(key, {})

    checked_raw = saved.get("checked_at")
    checked_dt = None
    if checked_raw:
        try:
            checked_dt = datetime.fromisoformat(checked_raw)
            if checked_dt.tzinfo is None:
                checked_dt = checked_dt.replace(tzinfo=PACIFIC)
            checked_dt = checked_dt.astimezone(PACIFIC)
            if latest_check is None or checked_dt > latest_check:
                latest_check = checked_dt
        except Exception:
            checked_dt = None

    status = saved.get("status", "WAITING FOR FIRST CHECK")
    price = saved.get("price")
    signal = saved.get("signal", "No hourly result saved yet")

    rows.append(
        {
            "City": store["city"],
            "Store": store["store"],
            "Address": store["address"],
            "Product": RETAILERS[store["store"]]["product"],
            "Status": status,
            "Price": f"${price:.2f}" if isinstance(price, (int, float)) else "—",
            "Last Checked": checked_dt.strftime("%-I:%M %p") if checked_dt else "—",
            "Signal": signal,
        }
    )

if latest_check:
    st.success(
        f"Latest hourly inventory check: "
        f"{latest_check.strftime('%b %-d, %Y at %-I:%M %p')} Pacific"
    )
else:
    st.warning(
        "No saved inventory result is available yet. "
        "Run the GitHub 'Hourly inventory check' workflow once."
    )

def status_icon(value):
    value = str(value).upper()

    if value == "IN STOCK":
        return "🟢 IN STOCK"
    if value == "OUT OF STOCK":
        return "🔴 OUT OF STOCK"
    if value == "NO LISTING":
        return "⚪ NO LISTING"
    if value == "CHECK MANUALLY":
        return "🟡 CHECK MANUALLY"
    if value == "WAITING FOR FIRST CHECK":
        return "⚪ WAITING FOR FIRST CHECK"
    return f"⚪ {value}"

df = pd.DataFrame(rows)
df["Status"] = df["Status"].map(status_icon)

st.subheader("Store inventory")
st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander("What the status means"):
    st.markdown(
        """
- **🟢 IN STOCK** — retailer-owned listing appears available.
- **🔴 OUT OF STOCK** — retailer listing explicitly reports unavailable.
- **⚪ NO LISTING** — no matching public product listing was detected.
- **🟡 CHECK MANUALLY** — retailer blocks or does not expose a reliable public inventory signal.
- **⚪ WAITING FOR FIRST CHECK** — GitHub has not yet saved an hourly result.

Third-party marketplace/reseller listings are excluded from restock alerts.
        """
    )

st.divider()
st.subheader("📱 Restock text alerts")

st.write(
    "Enter a U.S. mobile number. Alerts are sent only when the hourly monitor "
    "detects a change into **IN STOCK**."
)

with st.form("phone_form", clear_on_submit=False):
    phone = st.text_input("Mobile number", placeholder="(530) 555-1234")
    consent = st.checkbox("I agree to receive restock text alerts at this number.")
    submitted = st.form_submit_button("Save phone for alerts")

if submitted:
    if not consent:
        st.error("Please confirm consent before saving the number.")
    else:
        ok, message = save_subscriber(phone)
        st.success(message) if ok else st.error(message)

subscribers = load_subscribers()
if subscribers:
    st.caption(f"{len(subscribers)} phone number(s) currently enrolled.")

with st.expander("SMS setup / test"):
    st.write(
        "SMS uses Twilio. Add the Twilio credentials to Streamlit Secrets and GitHub Actions Secrets."
    )

    if st.button("Send test SMS", disabled=not bool(subscribers)):
        ok, message = send_test_sms()
        st.success(message) if ok else st.warning(message)

st.divider()
st.caption(
    "The dashboard itself never contacts retailer websites. "
    "The GitHub Action performs the inventory check once per hour."
)
