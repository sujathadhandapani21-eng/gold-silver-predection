# GoldenCast — Gold & Silver Price Prediction

A Flask dashboard for a precious-metal prediction academic project. It includes separate lightweight multivariate linear regression models for Gold and Silver, INR conversion, Indian market units, a historical chart, and a Render-ready deployment setup.

## Indian market display

- Gold: **₹ / gram**
- Silver: **₹ / gram**
- Reference conversion: `USD_TO_INR = 83.50` in `app.py` (replace with a live rate when you connect an API).

Current reference data added on 30 Sep 2026:

- 24K gold: **₹14,879 / gram** (₹1,48,790 / 10g)
- Silver: **₹240 / gram** (₹2,40,000 / kg)
- Source: [GoodReturns gold rates](https://www.goodreturns.in/gold-rates/) and [silver rates](https://www.goodreturns.in/silver-rates/). Rates vary by city, purity, GST, and dealer charges.

## Included data

`data/metal_prices.csv` contains daily rows from 2021-01-01 through 2026-09-30 with date, Gold USD/oz, Silver USD/oz, USD/INR reference rate, inflation, Gold ₹/gram, and Silver ₹/gram. The historical rows are deterministic project data calibrated to the current reference; they are not a live market feed.

## Daily dashboard

The home page shows Gold and Silver in separate cards, each with today's rate, tomorrow's prediction, a seven-day forecast, and a Refresh button. Use the date picker to check any date from 2021-01-01 onward. The JSON endpoint is `GET /api/daily?date=YYYY-MM-DD`.

The premium sample also includes a city selector, model confidence range around each forecast, KPI badges, and a **Snapshot** button that downloads a small text report. City adjustments are illustrative UI samples and should be replaced with a verified city-rate feed for production.

Additional sample modules now shown on the dashboard:

- Historical analytics with 7D / 30D / 90D / 1Y filters
- High, low, average, percentage change, and a Watch / Wait / Hold trend signal
- Browser-only price-alert demo saved with local storage
- Admin CSV upload preview control (UI sample; no server-side write yet)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## Deploy on Render

1. Push this folder to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Render automatically provides the `PORT` environment variable.

The current dataset is deterministic demo data so the website works immediately. Replace the generated arrays in `app.py` with your real CSV dataset when available.
