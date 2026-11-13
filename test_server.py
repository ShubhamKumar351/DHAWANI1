import os, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ["ADMIN_CONTACT"] = "admin@dhawani.test"; os.environ["ADMIN_PASSWORD"] = "adminpass123"
from app import create_app


def make():
    return create_app({"DATABASE": tempfile.mktemp(suffix=".db"), "TESTING": True})


def citizen(c, phone="9876543210"):
    r = c.post("/api/signup", json={"name": "Asha", "contact": "", "phone": phone, "password": "password1", "role": "citizen",
                                    "state": "Karnataka", "city": "Hubballi-Dharwad", "locality": "Vidya Nagar"})
    assert r.status_code == 201, r.json
    c.post("/api/verify", json={"code": r.json["demo_code"]})
    return r


def test_signup_verify_ticket_flow():
    c = make().test_client()
    assert c.post("/api/tickets", json={"text": "x", "category": "road"}).status_code == 401  # not logged in
    citizen(c)
    r = c.post("/api/tickets", json={"text": "big pothole near Market Road", "category": "road", "loc": "Market Road"})
    assert r.status_code == 201 and r.json["ticket"]["id"].startswith("GRV-")
    tid = r.json["ticket"]["id"]
    assert any(t["id"] == tid and t["owner"] for t in c.get("/api/tickets").json["tickets"])
    assert c.post("/api/tickets", json={"text": "x", "category": "hacked"}).status_code == 400
    assert c.patch(f"/api/tickets/{tid}", json={"status": "Resolved"}).status_code == 403  # citizens cannot change status


def test_unverified_citizen_cannot_file_and_wrong_otp():
    c = make().test_client()
    c.post("/api/signup", json={"name": "B", "phone": "9000000001", "password": "password1", "role": "citizen",
                                "state": "K", "city": "H", "locality": "L"})
    assert c.post("/api/tickets", json={"text": "x", "category": "road"}).status_code == 403
    assert c.post("/api/verify", json={"code": "000000"}).status_code == 400


def test_passwords_hashed_and_login():
    app = make(); c = app.test_client(); citizen(c)
    import db
    with app.app_context():
        assert "password1" not in db.get_db().execute("SELECT pw_hash FROM users").fetchone()[0]
    c.post("/api/logout", json={})
    assert c.post("/api/login", json={"contact": "9876543210", "password": "wrong"}).status_code == 401
    assert c.post("/api/login", json={"contact": "9876543210", "password": "password1"}).status_code == 200
    assert c.get("/api/me").json["user"]["name"] == "Asha"


def test_official_needs_admin_approval():
    app = make(); off, adm, cit = app.test_client(), app.test_client(), app.test_client()
    r = off.post("/api/signup", json={"name": "Ravi", "contact": "ravi@hubli.gov.in", "phone": "9111111111", "password": "password1",
                                      "role": "official", "dept": "Water board", "empId": "EMP1234", "proofName": "id.pdf"})
    assert r.status_code == 201 and not r.json["user"]["verified"]
    assert off.get("/api/admin/pending").status_code == 403
    assert off.patch("/api/tickets/GRV-1020", json={"status": "Resolved"}).status_code == 403  # pending officials cannot act
    adm.post("/api/login", json={"contact": "admin@dhawani.test", "password": "adminpass123"})
    pend = adm.get("/api/admin/pending").json["users"]
    assert len(pend) == 1
    assert adm.post(f"/api/admin/users/{pend[0]['id']}/approve", json={}).status_code == 200
    assert off.patch("/api/tickets/GRV-1020", json={"status": "Assigned"}).status_code == 200
    # a citizen on another device sees the official's change (shared database)
    citizen(cit)
    t = [x for x in cit.get("/api/tickets").json["tickets"] if x["id"] == "GRV-1020"][0]
    assert t["status"] == "Assigned" and t["demo"]


def test_bad_gov_email_duplicate_and_metoo():
    c = make().test_client()
    r = c.post("/api/signup", json={"name": "X", "contact": "x@gmail.com", "phone": "9222222222", "password": "password1", "role": "official",
                                    "empId": "EMP1", "proofName": "a"})
    assert r.status_code == 400
    citizen(c)
    assert c.post("/api/signup", json={"name": "A", "phone": "9876543210", "password": "password1", "role": "citizen",
                                       "state": "K", "city": "H", "locality": "L"}).status_code == 409
    assert c.post("/api/duplicates", json={"category": "water", "loc": "Gandhi Nagar"}).json["duplicate"]
    assert c.post("/api/tickets/GRV-1021/metoo", json={}).status_code == 200
    assert c.post("/api/tickets/GRV-1021/metoo", json={}).status_code == 409  # one me-too per user


def test_rate_limit_and_json_only():
    c = make().test_client()
    codes = [c.post("/api/login", json={"contact": "nobody@x.com", "password": "x"}).status_code for _ in range(12)]
    assert 429 in codes
    c2 = make().test_client(); citizen(c2)
    assert c2.post("/api/tickets", data="text=x", content_type="text/plain").status_code == 415
