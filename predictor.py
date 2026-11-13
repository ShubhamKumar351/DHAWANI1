"""Loads the trained scikit-learn models and analyses a citizen complaint."""
import json, re
from pathlib import Path
import joblib

MODEL_DIR = Path(__file__).parent
MIN_CONFIDENCE = 0.40  # below this we ask the citizen to rephrase instead of guessing

_models = joblib.load(MODEL_DIR / "dhawani.joblib")
METRICS = json.loads((MODEL_DIR / "metrics.json").read_text())

def detect_language(t):
    if re.search(r"[\u0C80-\u0CFF]", t):
        return "kn"
    if re.search(r"[\u0900-\u097F]", t):
        return "hi"
    return "en"


def extract_place(t):
    m = re.search(r"(?:near|at|opposite|behind|beside)\s+([A-Za-z0-9 .'’-]{3,28}?)(?:[,.]|\s+(?:for|since|is|has|are|from|very)\b|$)", t, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"([\u0C80-\u0CFF]+(?:\s[\u0C80-\u0CFF]+){0,2})\s*(?:ಹತ್ತಿರ|ಬಳಿ|ಮುಂದೆ|ಬದಿಯಲ್ಲಿ)", t)
    if m:
        return m.group(1).strip()
    m = re.search(r"([\u0900-\u097F]+(?:\s[\u0900-\u097F]+)?)\s*के\s*(?:पास|सामने)", t)
    return m.group(1).strip() if m else None


def analyze(text):
    text = text.strip()
    cat_proba = _models["category"].predict_proba([text])[0]
    classes = list(_models["category"].classes_)
    top = int(cat_proba.argmax())
    category, conf = classes[top], float(cat_proba[top])
    if category == "other" or conf < MIN_CONFIDENCE:
        category = None
    urg_proba = _models["urgency"].predict_proba([text])[0]
    urg_classes = list(_models["urgency"].classes_)
    urgency = urg_classes[int(urg_proba.argmax())]
    ranked = sorted(zip(classes, cat_proba), key=lambda x: -x[1])[:3]
    return {
        "language": detect_language(text),
        "category": category,
        "confidence": round(conf, 3),
        "urgency": urgency,
        "urgency_confidence": round(float(urg_proba.max()), 3),
        "place": extract_place(text),
        "top3": [{"category": c, "probability": round(float(p), 3)} for c, p in ranked],
    }
