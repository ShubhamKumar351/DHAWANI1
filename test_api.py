import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app import app

c = app.test_client()
CASES = [("Street light not working near Market Road", "streetlight", "medium"),
         ("गांधी नगर के पास पानी का पाइप फट गया है", "water", None),
         ("ಗಾಂಧಿ ನಗರದ ಹತ್ತಿರ ನೀರಿನ ಪೈಪ್ ಸೋರಿಕೆಯಾಗುತ್ತಿದೆ", "water", None),
         ("Open manhole near Station Road, very dangerous", "drainage", "high"),
         ("kachra nahi uthaya hai", "garbage", None)]


def test_categories():
    for text, cat, urg in CASES:
        j = c.post("/api/analyze", json={"text": text}).json
        assert j["category"] == cat, (text, j)
        if urg:
            assert j["urgency"] == urg, (text, j)


def test_unknown_and_validation():
    assert c.post("/api/analyze", json={"text": "hello good morning"}).json["category"] is None
    assert c.post("/api/analyze", json={"text": ""}).status_code == 400
    assert c.get("/").status_code == 200 and c.get("/api/model").json["metrics"]["samples"] > 0
