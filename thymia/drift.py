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

ABSOLUTE_THRESHOLD = 0.75  # if any score is above this, always flag
DRIFT_THRESHOLD    = 25    # if drift % is above this, flag

def analyse(sessions):
    if len(sessions) < 2:
        return {"message": "Need at least 2 sessions to detect drift"}
    
    baseline = get_baseline(sessions[:-1])
    current  = sessions[-1]
    drift    = get_drift(current, baseline)
    fields   = ["distress", "stress", "exhaustion", "sleep", "selfEsteem"]
    worst    = max(fields, key=lambda f: abs(current[f] - baseline[f]))

    # ── Check 1: drift from personal baseline ────────────────────────────
    drift_flag = drift > DRIFT_THRESHOLD

    # ── Check 2: absolute score too high regardless of drift ─────────────
    absolute_flag = any(current[f] > ABSOLUTE_THRESHOLD for f in fields)
    
    # ── Which biomarkers are critically high ─────────────────────────────
    critical = [f for f in fields if current[f] > ABSOLUTE_THRESHOLD]

    return {
        "drift_score":    drift,
        "direction":      get_trend(sessions),
        "worst_signal":   worst,
        "drift_flag":     drift_flag,       # changed a lot from YOUR normal
        "absolute_flag":  absolute_flag,    # still objectively too high
        "critical":       critical,         # which ones are critically high
        "flag":           drift_flag or absolute_flag  # either = alert
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