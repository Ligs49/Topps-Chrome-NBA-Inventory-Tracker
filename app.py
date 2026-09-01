from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from inventory import (
    CHECK_INTERVAL_SECONDS,
    get_inventory_snapshot,
    load_subscribers,
    save_subscriber,
    send_test_sms,
)

PACIFIC = ZoneInfo("America/Los_Angeles")

st.set_page_config(
    page_title="Topps 2026 Chrome NBA Inventory Tracker",
    page_icon="🏀",
    layout="wide",
)

# Refresh only the page display once per minute.
# Retailer checks remain cached for one hour.
st_autorefresh(interval=60_000, key="display_refresh")

st.title("🏀 Topps 2026 Chrome NBA Inventory Tracker")
st.caption("Davis & Woodland, California • Big 5 • Target • Walmart • Best Buy • CVS")

st.info(
    "Inventory checks are limited to once per hour. Reloading this page does not force another retailer check."
)

# Show page content immediately, then perform the inventory snapshot under a spinner.
with st.spinner("Loading latest inventory snapshot..."):
    snapshot = get_inventory_snapshot()

checked_at = snapshot["checked_at"]
next_check = checked_at + timedelta(seconds=CHECK_INTERVAL_SECONDS)
now = datetime.now(PACIFIC)
remaining = max(timedelta(0), next_check - now)

hours, rem = divmod(int(remaining.total_seconds()), 3600)
minutes, seconds = divmod(rem, 60)

c1, c2, c3 = st.columns(3)
c1.metric("Last inventory check", checked_at.strftime("%-I:%M %p"))
c2.metric("Next allowed check", next_check.strftime("%-I:%M %p"))
c3.metric("Time remaining", f"{hours:02d}:{minutes:02d}:{seconds:02d}")

st.subheader("Store inventory")

df = pd.DataFrame(snapshot["rows"])
display_cols = ["City", "Store", "Address", "Product", "Status", "Price", "Signal"]
df = df[display_cols]

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
    return "⚪ UNKNOWN"

df["Status"] = df["Status"].map(status_icon)
st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander("What the status means"):
    st.markdown(
        """
- **🟢 IN STOCK** — a retailer-owned listing appears available at or below the retail threshold.
- **🔴 OUT OF STOCK** — the monitored retailer listing explicitly reports unavailable.
- **⚪ NO LISTING** — no matching public product listing was found.
- **🟡 CHECK MANUALLY** — the site responded, but its public page did not provide a reliable inventory signal.

Third-party marketplace/reseller listings are intentionally excluded from restock alerts.
        """
    )

st.divider()
st.subheader("📱 Restock text alerts")
st.write(
    "Enter a U.S. mobile number. The tracker sends an alert only when a monitored status changes "
    "from unavailable/unknown to **IN STOCK**."
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

subs = load_subscribers()
if subs:
    st.caption(f"{len(subs)} phone number(s) currently enrolled.")

with st.expander("SMS setup / test"):
    st.write(
        "SMS uses Twilio. After TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER "
        "are added to Streamlit/GitHub secrets, you can send a test text."
    )
    if st.button("Send test SMS", disabled=not bool(subs)):
        ok, msg = send_test_sms()
        st.success(msg) if ok else st.warning(msg)

st.divider()
st.caption(
    "Retailer websites can change without notice. This app uses public retailer web signals "
    "and does not bypass CAPTCHAs, login walls, or anti-bot protections."
)
