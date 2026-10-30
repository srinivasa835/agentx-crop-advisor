import json, time, urllib.request
from tools import Tool


class RainForecast(Tool):
    name = "rain_forecast"
    description = ("Get rain probability and expected rainfall (mm) for the next few days at a location "
                   "using the free Open-Meteo service. Defaults to Tiruchirappalli.")
    args_doc = '{"latitude": float, "longitude": float, "days": int (1-7)}'

    def execute(self, latitude=10.79, longitude=78.70, days=3, **kwargs):
        try:
            lat, lon = float(latitude), float(longitude)
            days = max(1, min(int(days), 7))
        except Exception:
            return "Error: latitude, longitude and days must be numbers."
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lon}"
               "&daily=precipitation_probability_max,precipitation_sum,temperature_2m_max"
               f"&forecast_days={days}&timezone=auto")
        last_err = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    d = json.load(r)["daily"]
                rows = [{"date": d["time"][i],
                         "rain_probability_pct": d["precipitation_probability_max"][i],
                         "rain_mm": d["precipitation_sum"][i],
                         "max_temp_c": d["temperature_2m_max"][i]} for i in range(len(d["time"]))]
                top = max((r["rain_probability_pct"] or 0) for r in rows)
                risk = "HIGH" if top >= 60 else "MEDIUM" if top >= 30 else "LOW"
                return json.dumps({"rain_risk": risk, "total_rain_mm": round(sum((r["rain_mm"] or 0) for r in rows), 1),
                                   "forecast": rows})
            except Exception as e:
                last_err = e
                time.sleep(1 + attempt)
        return (f"Error: weather service unreachable ({last_err}). "
                "Use web_search to look up the rain forecast instead.")
