"""Builds the labelled training set (English, Hindi, Kannada and romanised Hindi/Kannada).

Honest note: this is a small hand-written dataset expanded with templates, so it is a
prototype. Replace it with real, anonymised citizen complaints for production."""
import itertools, json, random
from pathlib import Path

BASE = {
 "streetlight": [
  "street light not working", "the street lamp is broken", "lights are off on our road at night",
  "streetlight bulb has fused, it is very dark", "no lighting on the street",
  "स्ट्रीट लाइट खराब है", "सड़क की बत्ती नहीं जल रही", "गली में अंधेरा है, लाइट बंद है", "खंभे की लाइट बंद है",
  "ಬೀದಿ ದೀಪ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", "ಸ್ಟ್ರೀಟ್ ಲೈಟ್ ಉರಿಯುತ್ತಿಲ್ಲ", "ಕಂಬದ ದೀಪ ಹಾಳಾಗಿದೆ", "ಬೀದಿಯಲ್ಲಿ ಕತ್ತಲೆ ಇದೆ, ದೀಪ ಇಲ್ಲ",
  "street light kharab hai", "batti nahi jal rahi gali mein"],
 "drainage": [
  "drain is blocked", "sewage overflowing on the street", "open manhole on the road",
  "gutter overflow and bad smell", "drainage water is stagnant",
  "नाली जाम हो गई है", "सीवर का पानी सड़क पर बह रहा है", "मैनहोल खुला है", "नाली का पानी भर गया है",
  "ಚರಂಡಿ ಕಟ್ಟಿಕೊಂಡಿದೆ", "ಒಳಚರಂಡಿ ನೀರು ರಸ್ತೆಯಲ್ಲಿ ಹರಿಯುತ್ತಿದೆ", "ಮ್ಯಾನ್ ಹೋಲ್ ತೆರೆದಿದೆ", "ಚರಂಡಿ ನೀರು ನಿಂತಿದೆ",
  "naali band hai", "sewer overflow ho raha hai"],
 "road": [
  "big pothole on the road", "the road is broken with cracks", "damaged road, vehicles struggle",
  "deep pit in the middle of the road", "road repair needed urgently",
  "सड़क पर गड्ढा है", "सड़क टूटी हुई है", "सड़क में दरारें पड़ गई हैं", "सड़क की हालत बहुत खराब है",
  "ರಸ್ತೆಯಲ್ಲಿ ಗುಂಡಿ ಇದೆ", "ರಸ್ತೆ ಹಾಳಾಗಿದೆ", "ರಸ್ತೆ ಒಡೆದು ಹೋಗಿದೆ", "ರಸ್ತೆ ಗುಂಡಿ ಸರಿಪಡಿಸಿ",
  "sadak mein gadda hai", "road pe gundi hai"],
 "garbage": [
  "garbage not collected", "trash piled up near the corner", "waste dumped on the street, bad smell",
  "dustbin is overflowing", "no garbage pickup for a week",
  "कचरा नहीं उठाया गया", "कूड़े का ढेर लगा है", "कचरा गाड़ी नहीं आई", "कूड़ा सड़क पर फैला है",
  "ಕಸ ವಿಲೇವಾರಿ ಆಗಿಲ್ಲ", "ಕಸದ ರಾಶಿ ಬಿದ್ದಿದೆ", "ಕಸ ತುಂಬಿದೆ", "ಕಸದ ಗಾಡಿ ಬಂದಿಲ್ಲ",
  "kachra nahi uthaya", "kasa tumbide"],
 "water": [
  "water supply not coming", "pipe is leaking water", "tap has no water since morning",
  "borewell is not working", "water pipe burst near my house",
  "पानी नहीं आ रहा", "पाइप फट गया है, पानी बह रहा है", "नल में पानी नहीं है", "पानी की पाइप लाइन लीक हो रही है",
  "ನೀರು ಬರುತ್ತಿಲ್ಲ", "ನೀರಿನ ಪೈಪ್ ಸೋರಿಕೆಯಾಗುತ್ತಿದೆ", "ಕೊಳವೆ ಒಡೆದಿದೆ", "ನಲ್ಲಿಯಲ್ಲಿ ನೀರು ಇಲ್ಲ",
  "paani nahi aa raha", "neeru baruthilla"],
 "electricity": [
  "power cut in our area", "electric wire hanging low", "transformer is making a noise",
  "no electricity since last night", "voltage is very low at home",
  "बिजली नहीं है", "बिजली का तार लटक रहा है", "ट्रांसफार्मर में खराबी है", "रात से बिजली गुल है",
  "ವಿದ್ಯುತ್ ಇಲ್ಲ", "ವಿದ್ಯುತ್ ತಂತಿ ನೇತಾಡುತ್ತಿದೆ", "ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್ ಸಮಸ್ಯೆ ಇದೆ", "ಕರೆಂಟ್ ಇಲ್ಲ",
  "bijli nahi hai", "current kaat gaya hai"],
 "other": [
  "hello", "thank you", "how are you", "what is the weather today", "I want to know my property tax details",
  "where is the nearest hospital", "my ration card application status", "good morning sir",
  "नमस्ते", "धन्यवाद", "मेरा राशन कार्ड कहाँ बनेगा", "आज मौसम कैसा है", "आधार कार्ड कैसे बनवाएं",
  "ನಮಸ್ಕಾರ", "ಧನ್ಯವಾದಗಳು", "ನನ್ನ ಆಧಾರ್ ಕಾರ್ಡ್ ಬಗ್ಗೆ ಮಾಹಿತಿ ಬೇಕು", "ಇಂದು ಹವಾಮಾನ ಹೇಗಿದೆ", "ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ",
  "namaste", "kaise ho"],
}

# Danger phrases that make a complaint high urgency, per language.
DANGER = {
 "en": ["very dangerous", "live wire, please hurry", "accident happened here", "children are at risk, danger", "sparking and fire risk"],
 "hi": ["बहुत खतरनाक है", "तार गिरा हुआ है, खतरा है", "यहाँ दुर्घटना हो गई", "बच्चों को खतरा है"],
 "kn": ["ತುಂಬಾ ಅಪಾಯಕಾರಿ", "ತಂತಿ ಬಿದ್ದಿದೆ, ಅಪಾಯ ಇದೆ", "ಇಲ್ಲಿ ಅಪಘಾತ ಆಗಿದೆ", "ಮಕ್ಕಳಿಗೆ ಅಪಾಯ"],
}
PLACES = {
 "en": ["", " near Market Road", " near Station Road", " at Gandhi Nagar", " in ward 5", " since a week", " since 3 days"],
 "hi": ["", " गांधी नगर के पास", " बाजार रोड के सामने", " एक हफ्ते से", " वार्ड 5 में"],
 "kn": ["", " ಗಾಂಧಿ ನಗರದ ಹತ್ತಿರ", " ಮಾರುಕಟ್ಟೆ ರಸ್ತೆ ಬಳಿ", " ಒಂದು ವಾರದಿಂದ", " ವಾರ್ಡ್ 5 ರಲ್ಲಿ"],
}
PREFIX = {"en": ["", "Please fix: ", "Sir, "], "hi": ["", "कृपया ठीक करें: "], "kn": ["", "ದಯವಿಟ್ಟು ಸರಿಪಡಿಸಿ: "]}


def lang_of(t):
    if any("\u0c80" <= c <= "\u0cff" for c in t):
        return "kn"
    if any("\u0900" <= c <= "\u097f" for c in t):
        return "hi"
    return "en"


def build(seed=7):
    rnd = random.Random(seed)
    rows = []
    for cat, phrases in BASE.items():
        for gid, p in enumerate(phrases):
            lg = lang_of(p)
            group = f"{cat}:{gid}"
            combos = list(itertools.product(PREFIX[lg], PLACES[lg]))
            for pre, loc in rnd.sample(combos, min(6, len(combos))):
                rows.append((pre + p + loc, cat, "medium", group))
            if cat != "other":
                for d in rnd.sample(DANGER[lg], 2):
                    rows.append((p + ", " + d, cat, "high", group))
    # Keyword vocabulary (from the original site) as short training examples, one group per word.
    lex = json.loads((Path(__file__).parent / "lexicon.json").read_text(encoding="utf-8"))
    for cat, words in lex.items():
        for w in words:
            rows.append((w, cat, "medium", f"{cat}:kw:{w}"))
            rows.append((w + " problem", cat, "medium", f"{cat}:kw:{w}"))
    for t, c in [("live wire fallen on the road", "electricity"), ("open manhole very dangerous near school", "drainage"),
                 ("तार गिर गया है करंट का खतरा", "electricity"), ("खुला मैनहोल खतरा है", "drainage"),
                 ("ತೆರೆದ ಮ್ಯಾನ್ ಹೋಲ್ ಅಪಾಯಕಾರಿ", "drainage"), ("ವಿದ್ಯುತ್ ತಂತಿ ಬಿದ್ದಿದೆ ಅಪಾಯ", "electricity")]:
        rows.append((t, c, "high", f"{c}:nat:{t[:6]}"))
    return rows
