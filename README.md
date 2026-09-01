# Topps 2026 Chrome NBA Inventory Tracker

Simple Streamlit tracker for selected Davis and Woodland, California retailers.

## Stores

### Davis
- Big 5 — 1301 W Covell Blvd
- Target — 4601 2nd St
- CVS — 1471 W Covell Blvd
- CVS — 1550 E Covell Blvd

### Woodland
- Big 5 — 431 Pioneer Ave
- Target — 2185 Bronze Star Dr
- Walmart — 1720 E Main St
- Best Buy — 2165 Bronze Star Dr
- CVS — 7 W Main St

Davis currently has no Walmart or Best Buy location, so those chains are not shown there.

## What v1 does

- Checks public retailer web signals for 2025-26 Topps Chrome Updates Basketball.
- Limits the Streamlit app inventory fetch to once per hour.
- Has no manual inventory refresh button.
- Auto-updates the countdown display once per minute.
- Rejects obviously inflated marketplace/reseller prices using retailer-specific price ceilings.
- Lets a user enroll a U.S. phone number.
- Can send SMS through Twilio.
- Includes a GitHub Actions workflow intended to run `monitor.py` hourly.
- Sends a restock SMS only when a status transitions into `IN STOCK`.

## Important limitation

Retailer public webpages are not guaranteed to expose exact shelf inventory for every local store.
Target, Walmart, Best Buy, Big 5, and CVS can change their pages, JavaScript, APIs, anti-bot
rules, or pickup logic at any time.

This version intentionally does NOT bypass CAPTCHAs, login walls, or anti-bot protection.
It is a conservative first version. The next step is to strengthen each retailer adapter one
at a time for store-specific pickup inventory where the retailer exposes a usable public signal.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Twilio setup

Add these secrets in Streamlit Community Cloud and GitHub Actions:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

The phone numbers entered in the Streamlit app are saved to `subscribers.json`.

### Persistence warning

Streamlit Community Cloud's local filesystem should not be treated as a durable database.
For reliable multi-user phone enrollment, the next version should move subscribers to a
small persistent database such as Supabase. For a single-user first test, the local file
is enough to prove the flow.

## GitHub Actions

The included `.github/workflows/hourly_inventory.yml` runs once per hour.
GitHub scheduled workflows may start several minutes after the exact cron time.

The workflow commits `inventory_state.json` back to the repository so it can detect
out-of-stock -> in-stock transitions on later runs.
