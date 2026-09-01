import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from bs4 import BeautifulSoup

PACIFIC = ZoneInfo("America/Los_Angeles")
CHECK_INTERVAL_SECONDS = 3600

DATA_DIR = Path(__file__).parent
SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
STATE_FILE = DATA_DIR / "inventory_state.json"

PRODUCT_NAME = "2025-26 Topps Chrome Updates Basketball"

# Actual chain locations found in Davis/Woodland.
STORES = [
    {"city": "Davis", "store": "Big 5", "address": "1301 W Covell Blvd, Davis, CA 95616"},
    {"city": "Davis", "store": "Target", "address": "4601 2nd St, Davis, CA 95618"},
    {"city": "Davis", "store": "CVS", "address": "1471 W Covell Blvd, Davis, CA 95616"},
    {"city": "Davis", "store": "CVS", "address": "1550 E Covell Blvd, Davis, CA 95616"},
    {"city": "Woodland", "store": "Big 5", "address": "431 Pioneer Ave, Woodland, CA 95776"},
    {"city": "Woodland", "store": "Target", "address": "2185 Bronze Star Dr, Woodland, CA 95776"},
    {"city": "Woodland", "store": "Walmart", "address": "1720 E Main St, Woodland, CA 95776"},
    {"city": "Woodland", "store": "Best Buy", "address": "2165 Bronze Star Dr, Woodland, CA 95776"},
    {"city": "Woodland", "store": "CVS", "address": "7 W Main St, Woodland, CA 95695"},
]

# Retailer-owned/known product pages. Marketplace prices are rejected by max_price.
RETAILERS = {
    "Target": {
        "url": "https://www.target.com/p/-/A-1012663802",
        "product": "Chrome Updates Value Box",
        "max_price": 60.00,
    },
    "Walmart": {
        "url": "https://www.walmart.com/ip/20592405840",
        "product": "Chrome Updates Mega Box",
        "max_price": 100.00,
    },
    "Best Buy": {
        "url": "https://www.bestbuy.com/product/2025-2026-topps-chrome-update-series-basketball-blaster-box/J3ZPGXXLLX/sku/6678429",
        "product": "Chrome Updates Blaster Box",
        "max_price": 70.00,
    },
    "Big 5": {
        "url": "https://www.big5sportinggoods.com/store/search?Ntt=topps%20chrome%20basketball",
        "product": "Chrome Updates Basketball",
        "max_price": 100.00,
    },
    "CVS": {
        "url": "https://www.cvs.com/search?searchTerm=topps%20chrome%20basketball",
        "product": "Chrome Updates Basketball",
        "max_price": 100.00,
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def _extract_price(text):
    prices = []
    for raw in re.findall(r"\$(\d{1,4}(?:\.\d{2})?)", text):
        try:
            prices.append(float(raw))
        except ValueError:
            pass
    return min(prices) if prices else None

def _classify_page(retailer, html, max_price):
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    lower = text.lower()
    price = _extract_price(text)

    product_words = ("topps" in lower and "chrome" in lower and "basketball" in lower)
    if not product_words:
        return "NO LISTING", price, "No matching public product listing found"

    # Exclude obviously inflated third-party/marketplace pricing.
    if price is not None and price > max_price:
        return "CHECK MANUALLY", price, "Matching listing found, but price appears above retail threshold"

    out_terms = [
        "out of stock",
        "sold out",
        "currently unavailable",
        "not available",
        "pickup not available",
    ]
    in_terms = [
        "in stock",
        "add to cart",
        "add to basket",
        "pickup available",
        "ready for pickup",
    ]

    if any(term in lower for term in out_terms):
        return "OUT OF STOCK", price, "Retailer page reports unavailable"
    if any(term in lower for term in in_terms):
        return "IN STOCK", price, "Retailer-owned web listing appears available"

    return "CHECK MANUALLY", price, "Public page does not expose a reliable availability phrase"

def check_retailer(retailer):
    cfg = RETAILERS[retailer]
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=20)
        if r.status_code in (403, 429):
            return {
                "status": "CHECK MANUALLY",
                "price": None,
                "signal": f"Retailer blocked automated request ({r.status_code})",
            }
        r.raise_for_status()
        status, price, signal = _classify_page(retailer, r.text, cfg["max_price"])
        return {"status": status, "price": price, "signal": signal}
    except Exception as exc:
        return {
            "status": "CHECK MANUALLY",
            "price": None,
            "signal": f"Check failed: {type(exc).__name__}",
        }

@st.cache_data(ttl=CHECK_INTERVAL_SECONDS, show_spinner=False)
def get_inventory_snapshot():
    checked_at = datetime.now(PACIFIC)
    retailer_results = {name: check_retailer(name) for name in RETAILERS}
    rows = []

    for store in STORES:
        r = retailer_results[store["store"]]
        product = RETAILERS[store["store"]]["product"]
        rows.append(
            {
                "City": store["city"],
                "Store": store["store"],
                "Address": store["address"],
                "Product": product,
                "Status": r["status"],
                "Price": f"${r['price']:.2f}" if r["price"] is not None else "—",
                "Signal": r["signal"],
            }
        )

    return {"checked_at": checked_at, "rows": rows}

def _normalize_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None

def load_subscribers():
    if not SUBSCRIBERS_FILE.exists():
        return []
    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_subscriber(phone):
    normalized = _normalize_phone(phone)
    if not normalized:
        return False, "Enter a valid 10-digit U.S. mobile number."

    subscribers = load_subscribers()
    if normalized not in subscribers:
        subscribers.append(normalized)
        SUBSCRIBERS_FILE.write_text(json.dumps(subscribers, indent=2))
        return True, "Phone number saved for restock alerts."
    return True, "That phone number is already enrolled."

def _twilio_credentials():
    try:
        sid = st.secrets.get("TWILIO_ACCOUNT_SID")
        token = st.secrets.get("TWILIO_AUTH_TOKEN")
        from_num = st.secrets.get("TWILIO_FROM_NUMBER")
    except Exception:
        sid = token = from_num = None

    sid = sid or os.getenv("TWILIO_ACCOUNT_SID")
    token = token or os.getenv("TWILIO_AUTH_TOKEN")
    from_num = from_num or os.getenv("TWILIO_FROM_NUMBER")
    return sid, token, from_num

def _send_sms(to_number, body):
    sid, token, from_num = _twilio_credentials()
    if not all([sid, token, from_num]):
        return False, "Twilio secrets are not configured yet."

    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(body=body, from_=from_num, to=to_number)
        return True, "SMS sent."
    except Exception as exc:
        return False, f"SMS failed: {type(exc).__name__}"

def send_test_sms():
    subscribers = load_subscribers()
    if not subscribers:
        return False, "No phone number is enrolled."
    return _send_sms(
        subscribers[0],
        "Test: Topps 2026 Chrome NBA Inventory Tracker text alerts are working.",
    )
