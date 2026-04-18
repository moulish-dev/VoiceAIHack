import json
import os

HISTORY_FILE = "sessions.json"

def load_sessions():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_sessions(sessions):
    with open(HISTORY_FILE, "w") as f:
        json.dump(sessions, f, indent=2)

def get_baseline(sessions):
    return {
        "distress":   sum(s["distress"] for s in sessions) / len(sessions),
        "stress":     sum(s["stress"] for s in sessions) / len(sessions),
        "exhaustion": sum(s["exhaustion"] for s in sessions) / len(sessions),
        "sleep":      sum(s["sleep"] for s in sessions) / len(sessions),
        "selfEsteem": sum(s["selfEsteem"] for s in sessions) / len(sessions),
    }

def get_drift(current, baseline):
    fields = ["distress", "stress", "exhaustion", "sleep", "selfEsteem"]
    drift = sum(abs(current[f] - baseline[f]) for f in fields) / len(fields)
    return round(drift * 100, 1)

def get_trend(sessions, last_n=3):
    if len(sessions) < 2:
        return "stable"
    recent = [s["mentalStrain"] for s in sessions[-last_n:]]
    if recent[-1] > recent[0]:
        return "declining"
    elif recent[-1] < recent[0]:
        return "improving"
    return "stable"

def analyse(sessions):
    if len(sessions) < 2:
        return {"message": "Need at least 2 sessions to detect drift"}
    baseline = get_baseline(sessions[:-1])
    current  = sessions[-1]
    drift    = get_drift(current, baseline)
    fields   = ["distress", "stress", "exhaustion", "sleep", "selfEsteem"]
    worst    = max(fields, key=lambda f: abs(current[f] - baseline[f]))
    return {
        "drift_score":  drift,
        "direction":    get_trend(sessions),
        "worst_signal": worst,
        "flag":         drift > 25
    }

def extract_session(result):
    section = result["results"]["sections"][0]
    return {
        "timestamp":    result["completedAt"],
        "distress":     section["uniformDistress"]["value"],
        "stress":       section["uniformStress"]["value"],
        "exhaustion":   section["uniformExhaustion"]["value"],
        "sleep":        section["uniformSleepPropensity"]["value"],
        "selfEsteem":   section["uniformLowSelfEsteem"]["value"],
        "mentalStrain": section["mentalStrain"]["value"]
    }