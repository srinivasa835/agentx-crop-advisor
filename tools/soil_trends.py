import os, re, json
import numpy as np
import pandas as pd
from tools import Tool

KEYS = {
    "soil_moisture": ["soil moisture", "moisture"],
    "nitrogen": ["nitrogen"],
    "phosphorus": ["phosphorus"],
    "potassium": ["potassium"],
    "ph": ["ph"],
    "temperature": ["temperature", "temp"],
}


def _find(df, keywords):
    for kw in keywords:
        for c in df.columns:
            n = str(c).strip().lower()
            if kw == "ph":
                if re.match(r"^ph\b", n):
                    return c
            elif kw in n:
                return c
    return None


def _group_key(df, days):
    for c in df.columns:
        n = str(c).lower()
        if "date" in n or "time" in n:
            t = pd.to_datetime(df[c], errors="coerce")
            if t.notna().sum() > len(df) / 2:
                return t.dt.date.astype(str)
    for c in df.columns:
        if "day" in str(c).lower():
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > len(df) / 2:
                return s
    return pd.Series(np.arange(len(df)) * days // max(len(df), 1), index=df.index)


class SoilTrends(Tool):
    name = "analyze_soil_trends"
    description = ("Analyze the last N days of soil sensor data (moisture, N, P, K, pH, temperature) "
                   "from soil_telemetry.csv. Returns latest value, average and trend per metric.")
    args_doc = '{"days": int (default 7)}'

    def execute(self, days=7, **kwargs):
        try:
            days = max(1, int(days))
        except Exception:
            days = 7
        path = os.path.join(os.environ.get("AGENTX_DATA_DIR", "data"), "soil_telemetry.csv")
        try:
            df = pd.read_csv(path)
        except Exception as e:
            return f"Error: could not read {path}: {e}"
        if df.empty:
            return "Error: soil_telemetry.csv is empty. Tell the user no sensor data is available."

        cols = {k: _find(df, v) for k, v in KEYS.items()}
        cols = {k: c for k, c in cols.items() if c is not None}
        if not cols:
            return f"Error: no known sensor columns found. Columns are: {list(df.columns)}"

        for c in cols.values():
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["_k"] = _group_key(df, days)
        daily = df.groupby("_k")[list(cols.values())].mean().sort_index().tail(days)

        out = {"periods_used": len(daily), "metrics": {}}
        for name, c in cols.items():
            s = daily[c].dropna()
            if s.empty:
                continue
            first, last = float(s.iloc[0]), float(s.iloc[-1])
            pct = (last - first) / first * 100 if first else 0.0
            trend = "rising" if pct > 5 else "falling" if pct < -5 else "stable"
            out["metrics"][name] = {"first": round(first, 2), "latest": round(last, 2),
                                    "avg": round(float(s.mean()), 2),
                                    "change_pct": round(pct, 1), "trend": trend}
        return json.dumps(out)
