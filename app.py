"""Dhawani - multilingual citizen grievance redressal (Flask + SQLite + scikit-learn).
Hackathon prototype, not an official government service."""
import hashlib, os, re, secrets
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
import db
from security import current_user, rate_limit, require
from predictor import METRICS, analyze

CATS = {"streetlight", "drainage", "road", "garbage", "water", "electricity"}
STATUSES = ["Registered", "Assigned", "In progress", "Resolved"]
GOV_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.(gov\.in|nic\.in|gov)$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static", instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    key_file = Path(app.instance_path) / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or key_file.read_text(),
        DATABASE=os.environ.get("DATABASE", str(Path(app.instance_path) / "dhawani.db")),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",  # set to 1 behind HTTPS
        DEMO_OTP=os.environ.get("DEMO_OTP", "1") == "1",  # no SMS provider: show the code on screen
        MAX_CONTENT_LENGTH=64 * 1024)
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.init_db()
        ensure_admin(app)

    # ---------- helpers ----------
    def user_json(u):
        if not u:
            return None
        admin = u["role"] == "admin"
        return {"id": str(u["id"]), "name": u["name"], "contact": u["contact"], "phone": u["phone"],
                "role": "official" if admin else u["role"], "verified": bool(u["verified"]) or admin, "admin": admin,
                "state": u["state"] or "", "city": u["city"] or "", "locality": u["locality"] or "",
                "dept": u["dept"], "empId": u["emp_id"], "proof": {"name": u["proof_name"]} if u["proof_name"] else None}

    def ticket_json(t, me_id, mt):
        age = (datetime.now() - datetime.fromisoformat(t["created"])).days
        return {"id": f"GRV-{t['id']}", "cat": t["cat"], "loc": t["loc"] or "Not given", "ward": t["ward"], "urg": t["urg"],
                "status": t["status"], "age": age, "photo": bool(t["photo"]), "mt": mt, "demo": bool(t["demo"]),
                "owner": str(t["owner"]) if t["owner"] and t["owner"] == me_id else None,
                "city": t["city"] or "", "state": t["state"] or ""}

    def tid(ticket_id):
        m = re.fullmatch(r"GRV-(\d{1,9})", str(ticket_id).upper())
        return int(m.group(1)) if m else -1

    def all_tickets(me_id):
        d = db.get_db()
        counts = dict(d.execute("SELECT ticket_id, COUNT(*) FROM metoo GROUP BY ticket_id").fetchall())
        return [ticket_json(t, me_id, counts.get(t["id"], 0)) for t in d.execute("SELECT * FROM tickets ORDER BY id DESC")]

    def make_otp(uid):
        code = f"{secrets.randbelow(900000) + 100000}"
        db.get_db().execute("UPDATE users SET otp_hash=?, otp_expires=? WHERE id=?",
                            (generate_password_hash(code), (datetime.now() + timedelta(minutes=10)).isoformat(), uid))
        db.get_db().commit()
        return code

    # ---------- pages & ML ----------
    @app.get("/")
    def home():
                return send_from_directory(Path(__file__).parent, "index.html")

    @app.post("/api/analyze")
    @rate_limit(60)
    def api_analyze():
        text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
        if not text or len(text) > 1000:
            return jsonify(error="Send 1 to 1000 characters of text."), 400
        return jsonify(analyze(text))

    @app.get("/api/model")
    def api_model():
        return jsonify(model="TF-IDF char n-grams + logistic regression", metrics=METRICS)

    # ---------- auth ----------
    @app.post("/api/signup")
    @rate_limit(10)
    def signup():
        j = request.get_json(silent=True) or {}
        name, contact, phone = (j.get("name") or "").strip(), (j.get("contact") or "").strip().lower(), (j.get("phone") or "").strip()
        pw, role = j.get("password") or "", j.get("role")
        if role not in ("citizen", "official"):
            return jsonify(error="Choose citizen or official."), 400
        if not name or len(name) > 80:
            return jsonify(error="Please enter your name."), 400
        if not re.fullmatch(r"\d{10}", phone):
            return jsonify(error="Phone number must be exactly 10 digits."), 400
        if len(pw) < 8:
            return jsonify(error="Password must be at least 8 characters."), 400
        if role == "citizen" and not contact:
            contact = phone
        if contact != phone and not EMAIL.match(contact):
            return jsonify(error="Enter a valid email address."), 400
        extra = {"state": None, "city": None, "locality": None, "dept": None, "emp_id": None, "proof_name": None}
        if role == "citizen":
            for k in ("state", "city", "locality"):
                extra[k] = (j.get(k) or "").strip()[:80]
            if not all(extra[k] for k in ("state", "city", "locality")):
                return jsonify(error="Please select your state, city and locality."), 400
        else:
            if not GOV_EMAIL.match(contact):
                return jsonify(error="Officials must sign up with a government email ending in .gov.in or .nic.in."), 400
            extra.update(dept=(j.get("dept") or "")[:80], emp_id=(j.get("empId") or "").strip()[:40],
                         proof_name=(j.get("proofName") or "")[:120])
            if len(extra["emp_id"]) < 4 or not extra["proof_name"]:
                return jsonify(error="Enter your employee number and attach your proof document."), 400
        d = db.get_db()
        if d.execute("SELECT 1 FROM users WHERE contact=? OR (phone=? AND phone!='')", (contact, phone)).fetchone():
            return jsonify(error="An account with that email or phone number already exists. Log in instead."), 409
        cur = d.execute("INSERT INTO users(name,contact,phone,role,pw_hash,state,city,locality,dept,emp_id,proof_name,created) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (name, contact, phone, role, generate_password_hash(pw), extra["state"],
                        extra["city"], extra["locality"], extra["dept"], extra["emp_id"], extra["proof_name"], datetime.now().isoformat()))
        d.commit()
        session.clear(); session["uid"] = cur.lastrowid
        out = {"user": user_json(current_user())}
        if role == "citizen" and app.config["DEMO_OTP"]:
            out["demo_code"] = make_otp(cur.lastrowid)
        elif role == "citizen":
            make_otp(cur.lastrowid)  # TODO: send by SMS/email provider
        return jsonify(out), 201

    @app.post("/api/login")
    @rate_limit(10)
    def login():
        j = request.get_json(silent=True) or {}
        c = (j.get("contact") or "").strip().lower()
        digits = re.sub(r"\D", "", c) if re.fullmatch(r"[\d\s+-]+", c) else None
        u = db.get_db().execute("SELECT * FROM users WHERE " + ("phone=?" if digits else "contact=?"), (digits or c,)).fetchone()
        if not u or not check_password_hash(u["pw_hash"], j.get("password") or ""):
            return jsonify(error="Incorrect email/phone or password."), 401
        session.clear(); session["uid"] = u["id"]
        out = {"user": user_json(u)}
        if u["role"] == "citizen" and not u["verified"] and app.config["DEMO_OTP"]:
            out["demo_code"] = make_otp(u["id"])
        return jsonify(out)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        return jsonify(user=user_json(current_user()))

    @app.post("/api/otp/resend")
    @require()
    @rate_limit(5)
    def otp_resend(u):
        if u["role"] != "citizen" or u["verified"]:
            return jsonify(error="Nothing to verify."), 400
        code = make_otp(u["id"])
        return jsonify(demo_code=code if app.config["DEMO_OTP"] else None)

    @app.post("/api/verify")
    @require()
    @rate_limit(10)
    def verify(u):
        code = ((request.get_json(silent=True) or {}).get("code") or "").strip()
        ok = u["otp_hash"] and u["otp_expires"] and datetime.fromisoformat(u["otp_expires"]) > datetime.now() \
            and check_password_hash(u["otp_hash"], code)
        if not ok:
            return jsonify(error="That code is wrong or has expired."), 400
        db.get_db().execute("UPDATE users SET verified=1, otp_hash=NULL WHERE id=?", (u["id"],))
        db.get_db().commit()
        return jsonify(user=user_json(current_user()))

    # ---------- admin: approve government officials ----------
    @app.get("/api/admin/pending")
    @require("admin")
    def pending(u):
        rows = db.get_db().execute("SELECT * FROM users WHERE role='official' AND verified=0 ORDER BY id").fetchall()
        return jsonify(users=[user_json(r) for r in rows])

    @app.post("/api/admin/users/<int:uid>/<action>")
    @require("admin")
    def decide(u, uid, action):
        d = db.get_db()
        target = d.execute("SELECT * FROM users WHERE id=? AND role='official' AND verified=0", (uid,)).fetchone()
        if not target or action not in ("approve", "reject"):
            return jsonify(error="No such pending official."), 404
        d.execute("UPDATE users SET verified=1 WHERE id=?" if action == "approve" else "DELETE FROM users WHERE id=?", (uid,))
        d.commit()
        return jsonify(ok=True)

    # ---------- tickets ----------
    @app.get("/api/tickets")
    def list_tickets():
        u = current_user()
        return jsonify(tickets=all_tickets(u["id"] if u else None))

    @app.post("/api/duplicates")
    @require(verified=True)
    def duplicates(u):
        j = request.get_json(silent=True) or {}
        place = (j.get("loc") or u["locality"] or "")
        row = db.get_db().execute("SELECT id FROM tickets WHERE cat=? AND ward=? AND status!='Resolved' ORDER BY id DESC",
                                  (j.get("category"), db.ward_of(place))).fetchone()
        return jsonify(duplicate=f"GRV-{row['id']}" if row else None)

    @app.post("/api/tickets")
    @require(verified=True)
    @rate_limit(20)
    def create_ticket(u):
        j = request.get_json(silent=True) or {}
        text, cat = (j.get("text") or "").strip(), j.get("category")
        if not text or len(text) > 1000 or cat not in CATS:
            return jsonify(error="Describe the problem (up to 1000 characters) and choose a valid category."), 400
        place = (j.get("loc") or "").strip()[:120]
        urg = "high" if analyze(text)["urgency"] == "high" else "medium"  # decided by the server's model
        d = db.get_db()
        cur = d.execute("INSERT INTO tickets(cat,loc,ward,urg,text,photo,owner,state,city,locality,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (cat, place or "Not given", db.ward_of(place or u["locality"]), urg, text, int(bool(j.get("photo"))), u["id"],
                         u["state"], u["city"], u["locality"], datetime.now().isoformat()))
        d.commit()
        t = d.execute("SELECT * FROM tickets WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(ticket=ticket_json(t, u["id"], 0)), 201

    @app.patch("/api/tickets/<ticket_id>")
    @require("official")
    def set_status(u, ticket_id):
        status = (request.get_json(silent=True) or {}).get("status")
        if status not in STATUSES:
            return jsonify(error="Invalid status."), 400
        d = db.get_db()
        if not d.execute("UPDATE tickets SET status=? WHERE id=?", (status, tid(ticket_id))).rowcount:
            return jsonify(error="Ticket not found."), 404
        d.commit()
        return jsonify(ok=True)

    @app.post("/api/tickets/<ticket_id>/metoo")
    @require(verified=True)
    def metoo(u, ticket_id):
        d = db.get_db()
        t = d.execute("SELECT status FROM tickets WHERE id=?", (tid(ticket_id),)).fetchone()
        if not t or t["status"] == "Resolved":
            return jsonify(error="Ticket not found or already resolved."), 404
        try:
            d.execute("INSERT INTO metoo VALUES(?,?)", (tid(ticket_id), u["id"]))
            d.commit()
        except Exception:
            return jsonify(error="You already backed this ticket."), 409
        n = d.execute("SELECT COUNT(*) FROM metoo WHERE ticket_id=?", (tid(ticket_id),)).fetchone()[0]
        return jsonify(count=n)

    @app.patch("/api/me/location")
    @require()
    def set_location(u):
        j = request.get_json(silent=True) or {}
        vals = [(j.get(k) or "").strip()[:80] for k in ("state", "city", "locality")]
        if u["role"] != "citizen" or not all(vals):
            return jsonify(error="Select your state, city and locality."), 400
        db.get_db().execute("UPDATE users SET state=?, city=?, locality=? WHERE id=?", (*vals, u["id"]))
        db.get_db().commit()
        return jsonify(user=user_json(current_user()))

    @app.after_request
    def headers(r):
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        r.headers.setdefault("X-Frame-Options", "DENY")
        r.headers.setdefault("Referrer-Policy", "same-origin")
        return r

    return app


def ensure_admin(app):
    """Create the admin from ADMIN_CONTACT / ADMIN_PASSWORD env vars (never hardcode passwords)."""
    contact, pw = os.environ.get("ADMIN_CONTACT"), os.environ.get("ADMIN_PASSWORD")
    d = db.get_db()
    if contact and pw and len(pw) >= 8 and not d.execute("SELECT 1 FROM users WHERE contact=?", (contact.lower(),)).fetchone():
        d.execute("INSERT INTO users(name,contact,phone,role,pw_hash,verified,created) VALUES('Admin',?,'','admin',?,1,?)",
                  (contact.lower(), generate_password_hash(pw), datetime.now().isoformat()))
        d.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")  # debug is OFF unless you opt in locally
