import os, json
import pandas as pd
from tools import Tool

# Approximate target soil nutrient levels (mg/kg). Used when the crop is not in the reference CSV.
FALLBACK_TARGETS = {"tomato": (100, 50, 150), "rice": (80, 40, 40), "maize": (80, 45, 40),
                    "cotton": (120, 45, 25), "default": (90, 45, 60)}
KG_PER_ACRE_PER_MGKG = 0.81   # ~15 cm topsoil: 1 mg/kg is about 2 kg/ha
MAX_KG_PER_ACRE = 100         # safety cap per fertilizer


def _targets(crop):
    path = os.path.join(os.environ.get("AGENTX_DATA_DIR", "data"), "Crop_recommendation.csv")
    try:
        df = pd.read_csv(path)
        lab = [c for c in df.columns if c.lower() == "label"][0]
        sub = df[df[lab].str.lower() == crop.lower()]
        if not sub.empty:
            return (float(sub["N"].mean()), float(sub["P"].mean()), float(sub["K"].mean())), "Crop_recommendation.csv"
    except Exception:
        pass
    return FALLBACK_TARGETS.get(crop.lower(), FALLBACK_TARGETS["default"]), "built-in reference table"


class FertilizerDosage(Tool):
    name = "calculate_dosage"
    description = ("Compute fertilizer (urea, DAP, MOP) in kg and irrigation water in litres for a field, "
                   "from current soil N, P, K (mg/kg), crop name, area, and expected rain.")
    args_doc = ('{"crop": str, "nitrogen": float, "phosphorus": float, "potassium": float, '
                '"area_acres": float, "days": int, "expected_rain_mm": float, "etc_mm_per_day": float}')

    def execute(self, crop="tomato", nitrogen=0, phosphorus=0, potassium=0, area_acres=1,
                days=3, expected_rain_mm=0, etc_mm_per_day=5, **kwargs):
        try:
            n, p, k = float(nitrogen), float(phosphorus), float(potassium)
            area, days = float(area_acres), float(days)
            rain, etc = float(expected_rain_mm), float(etc_mm_per_day)
            if area <= 0:
                return "Error: area_acres must be positive."
        except Exception:
            return "Error: all numeric arguments must be numbers."

        (tn, tp, tk), source = _targets(str(crop))
        warnings = []

        def need(target, current):
            return max(0.0, target - current) * KG_PER_ACRE_PER_MGKG * area

        urea = need(tn, n) / 0.46
        dap = need(tp, p) * 2.29 / 0.46
        mop = need(tk, k) * 1.2 / 0.60
        out = {}
        for name, kg in (("urea_kg", urea), ("dap_kg", dap), ("mop_kg", mop)):
            cap = MAX_KG_PER_ACRE * area
            if kg > cap:
                warnings.append(f"{name} capped at {cap:.0f} kg (safety limit); split into several applications")
                kg = cap
            out[name] = round(kg, 1)

        net_mm = max(0.0, etc * days - rain)
        out["water_litres"] = round(net_mm * 4046.86 * area)
        out["net_water_mm"] = round(net_mm, 1)
        out["targets_mg_per_kg"] = {"N": round(tn), "P": round(tp), "K": round(tk), "source": source}
        out["warnings"] = warnings
        return json.dumps(out)
