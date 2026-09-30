from datetime import date, timedelta
import os
import numpy as np
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


@app.template_filter("inr")
def format_inr(value, decimals=2):
    """Format currency with Indian lakh/crore comma grouping."""
    amount = float(value)
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(amount):.{decimals}f}"
    if decimals:
        whole, fraction = formatted.split(".")
    else:
        whole, fraction = formatted, ""
    if len(whole) > 3:
        last = whole[-3:]
        prefix = whole[:-3]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        whole = ",".join(groups + [last])
    return f"{sign}₹{whole}" + (f".{fraction}" if decimals else "")

# Deterministic demo history. Replace these arrays with your real CSV dataset later.
_rng = np.random.default_rng(42)
START = date(2021, 1, 1)
DAYS = (date.today() - START).days + 1
_dates = [START + timedelta(days=i) for i in range(DAYS)]
_t = np.arange(DAYS, dtype=float)
_usd = 103 - 0.004 * _t + _rng.normal(0, 0.7, DAYS)
_inflation = 4.2 + 0.0015 * _t + _rng.normal(0, 0.18, DAYS)
_season = 18 * np.sin(2 * np.pi * _t / 365.25) + 7 * np.sin(2 * np.pi * _t / 30.5)
_gold_usd = 1780 + 0.55 * _t + 0.00005 * (_t ** 2) + _season + _rng.normal(0, 12, DAYS)
_silver_usd = 23 + 0.012 * _t + 0.000002 * (_t ** 2) + 1.7 * np.sin(2 * np.pi * _t / 365.25) + _rng.normal(0, 0.9, DAYS)

USD_TO_INR = 83.50
GRAMS_PER_OUNCE = 31.1035
CURRENT_GOLD_INR_PER_GRAM = 14879.00  # 24K reference, GoodReturns, 30 Sep 2026
CURRENT_SILVER_INR_PER_GRAM = 240.00  # Silver reference, GoodReturns, 30 Sep 2026
CITY_FACTORS = {"India": 1.0, "Mumbai": 1.0, "Chennai": 1.003, "Delhi": 1.001, "Hyderabad": 1.003}

# Calibrate the demo trend to the current India reference close so forecasts
# start from a realistic level while remaining fully reproducible offline.
_gold_target_usd = CURRENT_GOLD_INR_PER_GRAM * GRAMS_PER_OUNCE / USD_TO_INR
_silver_target_usd = CURRENT_SILVER_INR_PER_GRAM * GRAMS_PER_OUNCE / USD_TO_INR
_gold_usd *= _gold_target_usd / _gold_usd[-1]
_silver_usd *= _silver_target_usd / _silver_usd[-1]

def features(day_index, usd, inflation):
    x = float(day_index)
    return np.array([1.0, x, x * x / 1000, np.sin(2 * np.pi * x / 365.25),
                     np.cos(2 * np.pi * x / 365.25), usd, inflation], dtype=float)

_X = np.vstack([features(i, _usd[i], _inflation[i]) for i in range(DAYS)])
_GOLD_COEF, *_ = np.linalg.lstsq(_X, _gold_usd, rcond=None)
_SILVER_COEF, *_ = np.linalg.lstsq(_X, _silver_usd, rcond=None)
_GOLD_RMSE = float(np.sqrt(np.mean((_gold_usd - (_X @ _GOLD_COEF)) ** 2)))
_SILVER_RMSE = float(np.sqrt(np.mean((_silver_usd - (_X @ _SILVER_COEF)) ** 2)))
_GOLD_MAPE = float(np.mean(np.abs((_gold_usd - (_X @ _GOLD_COEF)) / _gold_usd)) * 100)


def index_for(d):
    return max(0, (d - START).days)


def predict_usd(target, usd, inflation, metal):
    coef = _GOLD_COEF if metal == "gold" else _SILVER_COEF
    return float(features(index_for(target), usd, inflation) @ coef)


def to_inr(value_usd, metal):
    return value_usd * USD_TO_INR / GRAMS_PER_OUNCE


def chart_payload(metal="gold"):
    series = _gold_usd if metal == "gold" else _silver_usd
    return [{"date": _dates[i].strftime("%b %Y"), "price": round(to_inr(float(series[i]), metal), 2)}
            for i in range(0, DAYS, 30)]


@app.route("/")
def index():
    today = date.today()
    return render_template(
        "index.html",
        today=today.isoformat(),
        default_usd=round(float(_usd[-1]), 2),
        default_inflation=round(float(_inflation[-1]), 2),
        current_gold=round(to_inr(float(_gold_usd[-1]), "gold"), 2),
        current_silver=round(to_inr(float(_silver_usd[-1]), "silver"), 2),
        gold_rmse=round(to_inr(_GOLD_RMSE, "gold"), 2),
        silver_rmse=round(to_inr(_SILVER_RMSE, "silver"), 2),
        mape=round(100 - _GOLD_MAPE, 2),
        chart_data=chart_payload(),
        usd_to_inr=USD_TO_INR,
        data_points=DAYS,
    )


@app.post("/predict")
def predict():
    try:
        payload = request.get_json(silent=True) or request.form
        target = date.fromisoformat(str(payload.get("target_date")))
        metal = str(payload.get("metal", "gold")).lower()
        if metal not in {"gold", "silver"}:
            raise ValueError("Choose Gold or Silver.")
        usd = float(payload.get("usd_index", 103))
        inflation = float(payload.get("inflation", 5))
        if not 50 <= usd <= 180 or not 0 <= inflation <= 30:
            raise ValueError("Input values are outside the supported range.")
        value_usd = predict_usd(target, usd, inflation, metal)
        baseline_usd = predict_usd(target, float(_usd[-1]), float(_inflation[-1]), metal)
        value = to_inr(value_usd, metal)
        baseline = to_inr(baseline_usd, metal)
        change = ((value - baseline) / baseline) * 100 if baseline else 0
        unit = "₹ / gram"
        return jsonify({
            "ok": True, "metal": metal.title(), "price": round(value, 2),
            "change": round(change, 2), "target_date": target.strftime("%d %b %Y"),
        "currency": unit, "exchange_rate": USD_TO_INR,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc) or "Please check your inputs."}), 400


@app.get("/api/history")
def history():
    metal = request.args.get("metal", "gold").lower()
    return jsonify(chart_payload(metal if metal in {"gold", "silver"} else "gold"))


@app.get("/api/analytics")
def analytics():
    metal = request.args.get("metal", "gold").lower()
    days = int(request.args.get("days", "30"))
    if metal not in {"gold", "silver"} or days not in {7, 30, 90, 365}:
        return jsonify({"ok": False, "error": "Choose Gold/Silver and 7, 30, 90, or 365 days."}), 400
    series = _gold_usd if metal == "gold" else _silver_usd
    sample = series[-min(days, len(series)):]
    prices = [round(to_inr(float(v), metal), 2) for v in sample]
    change = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] else 0
    direction = "Rising" if change > 0.25 else ("Falling" if change < -0.25 else "Stable")
    return jsonify({"ok": True, "metal": metal.title(), "days": days, "current": prices[-1], "high": max(prices), "low": min(prices), "average": round(sum(prices) / len(prices), 2), "change_percent": round(change, 2), "direction": direction, "series": prices})


@app.get("/api/daily")
def daily_forecast():
    """Return today, tomorrow, and a simple seven-day forecast for both metals."""
    today = date.today()
    requested = request.args.get("date")
    if requested:
        try:
            today = date.fromisoformat(requested)
        except ValueError:
            return jsonify({"ok": False, "error": "Use a valid date in YYYY-MM-DD format."}), 400
    if today < START:
        return jsonify({"ok": False, "error": f"Choose a date from {START.isoformat()} onward."}), 400
    city = request.args.get("city", "India")
    if city not in CITY_FACTORS:
        return jsonify({"ok": False, "error": "Choose a supported city."}), 400
    city_factor = CITY_FACTORS[city]
    usd = float(_usd[-1])
    inflation = float(_inflation[-1])
    output = {}
    for metal in ("gold", "silver"):
        rows = []
        for offset in range(0, 8):
            target = today + timedelta(days=offset)
            rows.append({
                "date": target.isoformat(),
                "label": "Today" if offset == 0 else ("Tomorrow" if offset == 1 else target.strftime("%a, %d %b")),
                "price": round(to_inr(predict_usd(target, usd, inflation, metal), metal) * city_factor, 2),
            })
        # The fetched reference applies only to the actual current day.
        if today == date.today():
            rows[0]["price"] = round((CURRENT_GOLD_INR_PER_GRAM if metal == "gold" else CURRENT_SILVER_INR_PER_GRAM) * city_factor, 2)
        confidence = 0.008 if metal == "gold" else 0.018
        for row in rows:
            row["low"] = round(row["price"] * (1 - confidence), 2)
            row["high"] = round(row["price"] * (1 + confidence), 2)
        output[metal] = rows
    return jsonify({"updated": today.isoformat(), "city": city, "source": "GoodReturns", "currency": "INR per gram", "metals": output})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
