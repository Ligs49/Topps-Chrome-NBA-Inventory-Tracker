import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from inventory import STORES, PRODUCTS, load_subscribers, save_subscriber, send_test_sms

PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_FILE = Path(__file__).parent / "inventory_state.json"

st.set_page_config(
    page_title="Topps 2026 Chrome NBA Inventory Tracker",
    page_icon="🏀",
    layout="wide",
)

# Display refresh only. It NEVER triggers retailer inventory checks.
st_autorefresh(interval=300_000, key="display_refresh")

st.title("🏀 Topps 2026 Chrome NBA Inventory Tracker")
st.caption(
    "Davis • Woodland • Napa • Fairfield • Suisun City • Vacaville"
)

st.info(
    "Retail inventory is checked by GitHub Actions once per hour. "
    "Refreshing this dashboard does not trigger another retailer check."
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
latest_check = None
rows = []

for store in STORES:
    key = f"{store['city']}|{store['store']}|{store['address']}"
    saved = state.get(key, {})

    checked_dt = None
    raw = saved.get("checked_at")
    if raw:
        try:
            checked_dt = datetime.fromisoformat(raw)
            if checked_dt.tzinfo is None:
                checked_dt = checked_dt.replace(tzinfo=PACIFIC)
            checked_dt = checked_dt.astimezone(PACIFIC)
            if latest_check is None or checked_dt > latest_check:
                latest_check = checked_dt
        except Exception:
            pass

    rows.append(
        {
            "City": store["city"],
            "Store": store["store"],
            "Address": store["address"],
            "Product": PRODUCTS[store["store"]]["name"],
            "Status": saved.get("status", "WAITING FOR FIRST CHECK"),
            "Price": saved.get("price"),
            "Last Checked": checked_dt.strftime("%-I:%M %p") if checked_dt else "—",
            "Signal": saved.get("signal", "No hourly result saved yet."),
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
        "Run GitHub → Actions → Hourly inventory check → Run workflow once."
    )

city_options = ["All"] + sorted({s["city"] for s in STORES})
city = st.selectbox("City", city_options, index=0)

df = pd.DataFrame(rows)
if city != "All":
    df = df[df["City"] == city].copy()

def render_status(status):
    status = str(status).upper()
    return {
        "IN STOCK": "🟢 IN STOCK",
        "OUT OF STOCK": "🔴 OUT OF STOCK",
        "ONLINE LISTING ONLY": "🔵 ONLINE LISTING ONLY",
        "NO LISTING": "⚪ NO LISTING",
        "CHECK MANUALLY": "🟡 CHECK MANUALLY",
        "WAITING FOR FIRST CHECK": "⚪ WAITING FOR FIRST CHECK",
    }.get(status, f"⚪ {status}")

df["Status"] = df["Status"].map(render_status)
df["Price"] = df["Price"].apply(
    lambda x: f"${x:.2f}" if isinstance(x, (int, float)) and x > 1 else "—"
)

st.subheader("Store inventory")
st.dataframe(
    df[["City","Store","Address","Product","Status","Price","Last Checked","Signal"]],
    use_container_width=True,
    hide_index=True,
)

with st.expander("What each status means"):
    st.markdown(
        """
- **🟢 IN STOCK** — the checker found a **local-store-specific** availability/pickup signal.
- **🔴 OUT OF STOCK** — the checker found local-store context and an unavailable/out-of-stock signal.
- **🔵 ONLINE LISTING ONLY** — the product is on the retailer website, but the selected local store was **not verified**. This does **not** send an alert.
- **🟡 CHECK MANUALLY** — the retailer blocked automation, timed out, requires login/JavaScript the checker could not resolve, or returned ambiguous local inventory. This does **not** send an alert.
- **⚪ NO LISTING** — no matching Topps Chrome basketball listing was detected.
- **⚪ WAITING FOR FIRST CHECK** — GitHub has not saved the first hourly check yet.

Only **IN STOCK** can trigger a restock text.
        """
    )

st.divider()
st.subheader("📱 Restock text alerts")
st.write(
    "For reliable hourly alerts, configure phone numbers in the GitHub Actions secret "
    "`ALERT_PHONE_NUMBERS` as comma-separated E.164 numbers, for example "
    "`+17075551234,+15305551234`."
)

with st.expander("Optional local Streamlit SMS test"):
    st.caption(
        "This form saves only on the current Streamlit instance and is intended for testing. "
        "Do not rely on it as the permanent hourly subscriber database."
    )
    with st.form("phone_form"):
        phone = st.text_input("Mobile number", placeholder="(707) 555-1234")
        consent = st.checkbox("I agree to receive a test/restock text at this number.")
        submitted = st.form_submit_button("Save test phone")
    if submitted:
        if not consent:
            st.error("Please confirm consent.")
        else:
            ok, msg = save_subscriber(phone)
            st.success(msg) if ok else st.error(msg)

    subscribers = load_subscribers()
    if subscribers and st.button("Send test SMS"):
        ok, msg = send_test_sms()
        st.success(msg) if ok else st.warning(msg)

st.divider()
st.caption(
    "The app does not bypass CAPTCHAs, authentication, or retailer anti-bot controls. "
    "When exact local inventory cannot be verified, it deliberately avoids claiming IN STOCK."
)
