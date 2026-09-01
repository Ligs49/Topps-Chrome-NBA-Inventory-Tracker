# Topps 2026 Chrome NBA Inventory Tracker v2

Tracks 2025-26 Topps Chrome Updates Basketball at selected Big 5, Target, Walmart, Best Buy, and CVS locations in:

- Davis
- Woodland
- Napa
- Fairfield
- Suisun City
- Vacaville

## v2 inventory logic

The tracker is deliberately conservative.

### IN STOCK
Only when a checker finds a local-store-specific availability/pickup signal.

### OUT OF STOCK
Local store context is found and the retailer reports unavailable/out of stock.

### ONLINE LISTING ONLY
The product is listed online, but the exact monitored store could not be verified.

### CHECK MANUALLY
The retailer blocked the check, timed out, required unresolved client-side/login behavior, or returned ambiguous inventory.

### NO LISTING
No matching public Topps Chrome basketball listing was detected.

Only a transition to **IN STOCK** sends a restock SMS.

## Retailer adapters

- Best Buy: official Best Buy developer API when `BESTBUY_API_KEY` is configured.
- Target: Playwright browser check with best-effort ZIP/store selection.
- Walmart: Playwright browser check with best-effort ZIP/store selection.
- Big 5: public web request, then Playwright fallback.
- CVS: public web request, then Playwright fallback.

The code does not bypass CAPTCHAs, login requirements, or anti-bot protections.

## Required GitHub Actions secrets for SMS

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `ALERT_PHONE_NUMBERS`

`ALERT_PHONE_NUMBERS` should contain comma-separated E.164 numbers:

`+17075551234,+15305551234`

## Optional Best Buy secret

Create a Best Buy developer API key and add:

- `BESTBUY_API_KEY`

Without it, Best Buy rows will show CHECK MANUALLY.

## Streamlit deployment

- Python 3.12
- Main file: `app.py`

The dashboard never performs retailer checks. GitHub Actions checks once per hour and commits `inventory_state.json`. The Streamlit dashboard reads that saved file.

## First run after uploading v2

1. Replace the repository files with the v2 files.
2. Commit.
3. Go to GitHub Actions.
4. Run **Hourly inventory check** manually once.
5. Wait for green success.
6. Reload the Streamlit dashboard.
