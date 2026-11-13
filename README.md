# Dhawani – Multilingual Citizen Grievance Redressal (Python full stack + ML)

Hackathon prototype, not an official government service. Citizens report civic problems in
Kannada, Hindi or English (text or voice). A scikit-learn model predicts category and urgency;
tickets live in a shared SQLite database so citizens and officials on different devices see the same data.

## Run locally

Mac / Linux:

```bash
pip install -r requirements.txt
export ADMIN_CONTACT=admin@yourmail.com
export ADMIN_PASSWORD='choose-a-long-password'   # creates the admin once
python app.py                                     # http://127.0.0.1:5000
python train.py                                   # optional: retrain the model
```

Windows (cmd):

```bat
pip install -r requirements.txt
set ADMIN_CONTACT=admin@yourmail.com
set ADMIN_PASSWORD=choose-a-long-password
python app.py
python train.py
```

## What is real now

- **Shared database** (SQLite, `db.py`): users, tickets, "me too" votes. Open the site on two devices and they stay in sync.
- **Server-side login** (`app.py`, `security.py`): passwords hashed with werkzeug, signed HttpOnly session cookies,
  roles enforced on the server (citizen / official / admin). Officials need admin approval; only verified officials can change a status.
- **Safe defaults**: debug is off (`FLASK_DEBUG=1` only for local work), secret key generated into `instance/`,
  per-IP rate limits, JSON-only writes, security headers, request size limit, tickets' complaint text never sent to other users.
- **ML** (`train.py`, `data.py`, `predictor.py`, `lexicon.json`): TF-IDF + logistic regression, about 84% cross-validated
  category accuracy on a small synthetic dataset. The trained model is saved as `dhawani.joblib` (metrics in `metrics.json`).
- **Tests**: `test_server.py`, `test_api.py` (pytest) and `e2e_browser.py` (Playwright, needs the server running).

## Project structure

```
app.py          Flask app and API routes
db.py           SQLite database layer
security.py     Login, roles, rate limiting, security headers
predictor.py    Loads the model and predicts category and urgency
train.py        Trains the model
data.py         Training data
lexicon.json    Multilingual keyword lexicon
index.html      Frontend
test_*.py       Tests
e2e_browser.py  Browser end-to-end test
Procfile        Deployment start command
```

## Still a prototype

- One-time codes are shown on screen when `DEMO_OTP=1`. Connect an SMS/email provider and set `DEMO_OTP=0` for real verification.
- Ward = a stable hash of the locality name (demo grid), not real ward boundaries or GPS.
- Photo analysis and department routing are simulated; official proof documents are not uploaded (file name only).
- Seven demo tickets (GRV-1018 to GRV-1024) are seeded and marked "demo".
- Rate limiting is per process; use Flask-Limiter + Redis for several workers. SQLite suits a demo, not heavy traffic.
- The training data is small and partly template-generated; collect real anonymised complaints before trusting the numbers.

## Deploy (example)

```bash
COOKIE_SECURE=1 ADMIN_CONTACT=... ADMIN_PASSWORD=... gunicorn app:app --workers 1
# DEMO_OTP=1 shows OTPs on screen: demo only. Use DEMO_OTP=0 once an SMS/email provider is connected.
```

Serve over HTTPS and keep `instance/` on persistent storage. Never commit `secret_key`, `instance/` or any `.db` file.

## License

MIT (see `LICENSE`).
