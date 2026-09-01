import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

PACIFIC = ZoneInfo("America/Los_Angeles")
REQUEST_TIMEOUT = 15
BROWSER_TIMEOUT_MS = 20000
MAX_WORKERS = 4
DATA_DIR = Path(__file__).parent
SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"

STORES = [{'city': 'Davis', 'store': 'Big 5', 'address': '1301 W Covell Blvd, Davis, CA 95616', 'zip': '95616'}, {'city': 'Davis', 'store': 'Target', 'address': '4601 2nd St, Davis, CA 95618', 'zip': '95618'}, {'city': 'Davis', 'store': 'CVS', 'address': '1471 W Covell Blvd, Davis, CA 95616', 'zip': '95616'}, {'city': 'Davis', 'store': 'CVS', 'address': '1550 E Covell Blvd, Davis, CA 95616', 'zip': '95616'}, {'city': 'Woodland', 'store': 'Big 5', 'address': '431 Pioneer Ave, Woodland, CA 95776', 'zip': '95776'}, {'city': 'Woodland', 'store': 'Target', 'address': '2185 Bronze Star Dr, Woodland, CA 95776', 'zip': '95776'}, {'city': 'Woodland', 'store': 'Walmart', 'address': '1720 E Main St, Woodland, CA 95776', 'zip': '95776', 'walmart_store': '2190'}, {'city': 'Woodland', 'store': 'Best Buy', 'address': '2165 Bronze Star Dr, Woodland, CA 95776', 'zip': '95776'}, {'city': 'Woodland', 'store': 'CVS', 'address': '7 W Main St, Woodland, CA 95695', 'zip': '95695'}, {'city': 'Napa', 'store': 'Big 5', 'address': '1305 Trancas St, Napa, CA 94558', 'zip': '94558'}, {'city': 'Napa', 'store': 'Target', 'address': '205 Soscol Ave, Napa, CA 94559', 'zip': '94559'}, {'city': 'Napa', 'store': 'Target', 'address': '4000 Bel Aire Plaza, Napa, CA 94558', 'zip': '94558'}, {'city': 'Napa', 'store': 'Walmart', 'address': '681 Lincoln Ave, Napa, CA 94558', 'zip': '94558', 'walmart_store': '2925'}, {'city': 'Napa', 'store': 'CVS', 'address': '291 S Coombs St, Napa, CA 94559', 'zip': '94559'}, {'city': 'Napa', 'store': 'CVS', 'address': '675 Trancas St, Napa, CA 94558', 'zip': '94558'}, {'city': 'Napa', 'store': 'CVS', 'address': '1558 Trancas St, Napa, CA 94558', 'zip': '94558'}, {'city': 'Fairfield', 'store': 'Big 5', 'address': '1320 Gateway Blvd Ste M2, Fairfield, CA 94533', 'zip': '94533'}, {'city': 'Fairfield', 'store': 'Target', 'address': '2059 Cadenasso Dr, Fairfield, CA 94533', 'zip': '94533'}, {'city': 'Fairfield', 'store': 'Walmart', 'address': '2701 N Texas St, Fairfield, CA 94533', 'zip': '94533', 'walmart_store': '2048'}, {'city': 'Fairfield', 'store': 'CVS', 'address': '300 Travis Blvd, Fairfield, CA 94533', 'zip': '94533'}, {'city': 'Fairfield', 'store': 'CVS', 'address': '5059 Business Center Dr, Fairfield, CA 94534', 'zip': '94534'}, {'city': 'Suisun City', 'store': 'Walmart', 'address': '350 Walters Rd, Suisun City, CA 94585', 'zip': '94585', 'walmart_store': '3708'}, {'city': 'Vacaville', 'store': 'Big 5', 'address': '2030 Harbison Dr, Vacaville, CA 95687', 'zip': '95687'}, {'city': 'Vacaville', 'store': 'Target', 'address': '3000 Harbison Dr, Vacaville, CA 95687', 'zip': '95687'}, {'city': 'Vacaville', 'store': 'Walmart', 'address': '1501 Helen Power Dr, Vacaville, CA 95687', 'zip': '95687', 'walmart_store': '1704'}, {'city': 'Vacaville', 'store': 'Best Buy', 'address': '1621 E Monte Vista Ave Ste A, Vacaville, CA 95688', 'zip': '95688'}, {'city': 'Vacaville', 'store': 'CVS', 'address': '625 Elmira Rd, Vacaville, CA 95687', 'zip': '95687'}]

PRODUCTS = {
    "Target": {
        "name": "2025-26 Topps Chrome Updates Basketball Value Box",
        "url": "https://www.target.com/p/-/A-1012663802",
        "max_price": 70.00,
    },
    "Walmart": {
        "name": "2025-26 Topps Chrome Updates Basketball Mega Box",
        "url": "https://www.walmart.com/ip/20592405840",
        "max_price": 120.00,
    },
    "Best Buy": {
        "name": "2025-26 Topps Chrome Updates Basketball Blaster Box",
        "url": "https://www.bestbuy.com/product/2025-2026-topps-chrome-update-series-basketball-blaster-box/J3ZPGXXLLX/sku/6678429",
        "sku": "6678429",
        "max_price": 80.00,
    },
    "Big 5": {
        "name": "Topps Chrome Updates Basketball",
        "url": "https://www.big5sportinggoods.com/store/search?Ntt=topps%20chrome%20basketball",
        "max_price": 120.00,
    },
    "CVS": {
        "name": "Topps Chrome Updates Basketball",
        "url": "https://www.cvs.com/search?searchTerm=topps%20chrome%20basketball",
        "max_price": 120.00,
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

def clean_price(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value <= 1.00 or value > 500:
        return None
    return value

def extract_prices(text):
    prices = []
    for raw in re.findall(r"\$(\d{1,4}(?:\.\d{2})?)", text or ""):
        p = clean_price(raw)
        if p is not None:
            prices.append(p)
    return prices

def choose_price(text, max_price):
    prices = [p for p in extract_prices(text) if p <= max_price]
    return min(prices) if prices else None

def result(status, signal, price=None, source=""):
    return {
        "status": status,
        "signal": signal,
        "price": clean_price(price),
        "source": source,
    }

def address_tokens(store):
    # Use city + street number as a conservative local-store signature.
    number = re.match(r"(\d+)", store["address"])
    tokens = [store["city"].lower()]
    if number:
        tokens.append(number.group(1))
    return tokens

def local_context_present(text, store):
    lower = (text or "").lower()
    return all(tok in lower for tok in address_tokens(store))

def classify_local_text(text, store, max_price):
    lower = (text or "").lower()
    price = choose_price(text, max_price)

    product_present = "topps" in lower and "chrome" in lower and "basketball" in lower
    if not product_present:
        return result("NO LISTING", "No matching Topps Chrome basketball listing found.", price)

    local = local_context_present(text, store)

    local_in_phrases = [
        "pickup available", "ready for pickup", "pickup today",
        "in stock", "available for pickup", "get it today",
    ]
    local_out_phrases = [
        "pickup not available", "out of stock", "not available at this store",
        "unavailable for pickup", "sold out",
    ]

    if local and any(p in lower for p in local_out_phrases):
        return result("OUT OF STOCK", "Local store context found and pickup is unavailable.", price)

    if local and any(p in lower for p in local_in_phrases):
        return result("IN STOCK", "Local store context found with an in-stock/pickup signal.", price)

    generic_online = any(p in lower for p in ["add to cart", "shipping", "ship it", "delivery"])
    if generic_online:
        return result(
            "ONLINE LISTING ONLY",
            "Product is listed online, but local-store pickup could not be verified.",
            price,
        )

    return result(
        "CHECK MANUALLY",
        "Product page loaded, but no reliable local-store inventory signal was exposed.",
        price,
    )

def requests_check(store):
    cfg = PRODUCTS[store["store"]]
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code in (401, 403, 429):
            return result("CHECK MANUALLY", f"Retailer blocked automated request (HTTP {r.status_code}).")
        r.raise_for_status()
        return classify_local_text(r.text, store, cfg["max_price"])
    except requests.Timeout:
        return result("CHECK MANUALLY", "Retailer request timed out.")
    except requests.RequestException as exc:
        return result("CHECK MANUALLY", f"Retailer request failed: {type(exc).__name__}")

def browser_check(store):
    cfg = PRODUCTS[store["store"]]
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except Exception:
        return result("CHECK MANUALLY", "Playwright is not installed in this environment.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1440, "height": 1100},
            )
            page = context.new_page()
            page.set_default_timeout(BROWSER_TIMEOUT_MS)
            page.goto(cfg["url"], wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)

            # Give client-side inventory widgets time to render.
            page.wait_for_timeout(2500)

            # Best-effort store/ZIP selection. Retailer UI changes frequently,
            # so failures here intentionally fall through to a conservative status.
            zip_code = store["zip"]

            # Target patterns
            if store["store"] == "Target":
                for label in ["Edit store", "Change store", "Check other stores"]:
                    try:
                        loc = page.get_by_text(label, exact=False).first
                        if loc.is_visible(timeout=1200):
                            loc.click()
                            page.wait_for_timeout(700)
                            break
                    except Exception:
                        pass
                for selector in [
                    'input[placeholder*="ZIP"]',
                    'input[aria-label*="ZIP"]',
                    'input[placeholder*="city"]',
                    'input[type="search"]',
                ]:
                    try:
                        box = page.locator(selector).first
                        if box.is_visible(timeout=900):
                            box.fill(zip_code)
                            box.press("Enter")
                            page.wait_for_timeout(1800)
                            break
                    except Exception:
                        pass

            # Walmart patterns
            elif store["store"] == "Walmart":
                for phrase in ["Pickup", "How do you want your items", "Set location", "Change"]:
                    try:
                        loc = page.get_by_text(phrase, exact=False).first
                        if loc.is_visible(timeout=1000):
                            loc.click()
                            page.wait_for_timeout(600)
                            break
                    except Exception:
                        pass
                for selector in [
                    'input[placeholder*="ZIP"]',
                    'input[aria-label*="ZIP"]',
                    'input[placeholder*="address"]',
                    'input[type="search"]',
                ]:
                    try:
                        box = page.locator(selector).first
                        if box.is_visible(timeout=900):
                            box.fill(zip_code)
                            box.press("Enter")
                            page.wait_for_timeout(1800)
                            break
                    except Exception:
                        pass

            # Big 5 / CVS: browser execution can reveal JS-rendered results,
            # but we still require a local signature before declaring IN STOCK.
            page.wait_for_timeout(1200)
            text = page.locator("body").inner_text(timeout=BROWSER_TIMEOUT_MS)
            browser.close()
            return classify_local_text(text, store, cfg["max_price"])

    except PlaywrightTimeoutError:
        return result("CHECK MANUALLY", "Browser check timed out.")
    except Exception as exc:
        return result("CHECK MANUALLY", f"Browser check failed: {type(exc).__name__}")

def bestbuy_api_check(store):
    cfg = PRODUCTS["Best Buy"]
    api_key = os.getenv("BESTBUY_API_KEY")
    if not api_key:
        return result(
            "CHECK MANUALLY",
            "Best Buy API key not configured. Add BESTBUY_API_KEY to GitHub Actions secrets.",
            source="Best Buy API",
        )

    # Best Buy supports compound product + store queries.
    # We query the product SKU plus stores near the store ZIP and then require
    # the returned store city/ZIP to match the monitored location.
    query = f"products(sku={cfg['sku']})+stores(area({store['zip']},15))"
    url = f"https://api.bestbuy.com/v1/{query}"
    params = {
        "apiKey": api_key,
        "format": "json",
        "show": "sku,name,salePrice,inStoreAvailability,stores",
    }

    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code in (401, 403):
            return result("CHECK MANUALLY", "Best Buy API rejected the API key.", source="Best Buy API")
        r.raise_for_status()
        data = r.json()

        products = data.get("products") or []
        if not products:
            return result("NO LISTING", "Best Buy API returned no matching SKU.", source="Best Buy API")

        product = products[0]
        price = clean_price(product.get("salePrice"))
        stores = product.get("stores") or data.get("stores") or []

        city = store["city"].lower()
        zipcode = store["zip"]
        matching = []
        for s in stores:
            blob = json.dumps(s).lower()
            if city in blob or zipcode in blob:
                matching.append(s)

        if matching:
            blob = json.dumps(matching).lower()
            if any(x in blob for x in ['"inStoreAvailability":true', '"inStoreAvailability": true', '"available":true', '"available": true']):
                return result("IN STOCK", "Best Buy API reports local in-store availability.", price, "Best Buy API")
            if any(x in blob for x in ['"inStoreAvailability":false', '"inStoreAvailability": false', '"available":false', '"available": false']):
                return result("OUT OF STOCK", "Best Buy API reports local store unavailable.", price, "Best Buy API")

        # If compound API shape changes, retain conservative result rather than guessing.
        if product.get("inStoreAvailability") is True:
            return result(
                "ONLINE LISTING ONLY",
                "Best Buy reports in-store availability somewhere, but the monitored store was not verified.",
                price,
                "Best Buy API",
            )

        return result(
            "CHECK MANUALLY",
            "Best Buy API returned the product, but exact monitored-store availability was not resolved.",
            price,
            "Best Buy API",
        )

    except requests.RequestException as exc:
        return result("CHECK MANUALLY", f"Best Buy API request failed: {type(exc).__name__}", source="Best Buy API")
    except ValueError:
        return result("CHECK MANUALLY", "Best Buy API returned invalid JSON.", source="Best Buy API")

def check_store(store):
    if store["store"] == "Best Buy":
        return bestbuy_api_check(store)

    # Target and Walmart benefit most from a real browser because store inventory
    # is normally injected after location/store selection.
    if store["store"] in ("Target", "Walmart"):
        return browser_check(store)

    # Big 5 / CVS: quick public request first; if it is ambiguous, try browser JS.
    first = requests_check(store)
    if first["status"] in ("IN STOCK", "OUT OF STOCK", "NO LISTING"):
        return first
    second = browser_check(store)
    return second

def check_all_stores():
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {
            pool.submit(check_store, store): i
            for i, store in enumerate(STORES)
        }
        for future in as_completed(future_map):
            i = future_map[future]
            try:
                results[i] = future.result()
            except Exception as exc:
                results[i] = result("CHECK MANUALLY", f"Unhandled checker error: {type(exc).__name__}")

    return [results[i] for i in range(len(STORES))]

def normalize_phone(phone):
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
    normalized = normalize_phone(phone)
    if not normalized:
        return False, "Enter a valid 10-digit U.S. mobile number."
    subscribers = load_subscribers()
    if normalized not in subscribers:
        subscribers.append(normalized)
        SUBSCRIBERS_FILE.write_text(json.dumps(subscribers, indent=2))
        return True, "Phone number saved on this Streamlit instance."
    return True, "That phone number is already enrolled on this Streamlit instance."

def twilio_credentials():
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    try:
        import streamlit as st
        sid = sid or st.secrets.get("TWILIO_ACCOUNT_SID")
        token = token or st.secrets.get("TWILIO_AUTH_TOKEN")
        from_number = from_number or st.secrets.get("TWILIO_FROM_NUMBER")
    except Exception:
        pass
    return sid, token, from_number

def send_sms(to_number, body):
    sid, token, from_number = twilio_credentials()
    if not all([sid, token, from_number]):
        return False, "Twilio is not configured."
    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(body=body, from_=from_number, to=to_number)
        return True, "SMS sent."
    except Exception as exc:
        return False, f"SMS failed: {type(exc).__name__}"

def send_test_sms():
    subscribers = load_subscribers()
    if not subscribers:
        return False, "No phone number is enrolled on this Streamlit instance."
    return send_sms(
        subscribers[0],
        "Test: Topps 2026 Chrome NBA Inventory Tracker alerts are working."
    )
