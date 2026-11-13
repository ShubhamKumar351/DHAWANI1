"""SQLite database layer (shared by citizens and officials)."""
import sqlite3, hashlib, os
from datetime import datetime, timedelta
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, contact TEXT UNIQUE NOT NULL,
  phone TEXT, role TEXT NOT NULL DEFAULT 'citizen', pw_hash TEXT NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0, state TEXT, city TEXT, locality TEXT,
  dept TEXT, emp_id TEXT, proof_name TEXT, otp_hash TEXT, otp_expires TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS tickets(
  id INTEGER PRIMARY KEY, cat TEXT NOT NULL, loc TEXT, ward INTEGER, urg TEXT, status TEXT NOT NULL DEFAULT 'Registered',
  text TEXT, photo INTEGER DEFAULT 0, owner INTEGER REFERENCES users(id), state TEXT, city TEXT, locality TEXT,
  demo INTEGER DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metoo(
  ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER NOT NULL REFERENCES users(id),
  PRIMARY KEY(ticket_id, user_id));
"""
# Demo tickets that ship with the prototype so the dashboard is not empty. Flagged demo=1.
DEMO = [(1020, "water", "Gandhi Nagar", 3, "high", "In progress", 4), (1021, "water", "Gandhi Nagar", 3, "medium", "Assigned", 2),
        (1022, "water", "Gandhi Nagar", 3, "medium", "Registered", 1), (1023, "road", "Temple Street", 5, "medium", "Assigned", 3),
        (1024, "drainage", "Station Road", 2, "high", "Registered", 0), (1019, "garbage", "Bazaar Lane", 7, "medium", "Resolved", 5),
        (1018, "streetlight", "Lake View", 1, "medium", "In progress", 2)]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_=None):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db(seed_demo=True):
    d = get_db()
    d.executescript(SCHEMA)
    if seed_demo and d.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
        for n, cat, loc, ward, urg, st, age in DEMO:
            d.execute("INSERT INTO tickets(id,cat,loc,ward,urg,status,demo,created) VALUES(?,?,?,?,?,?,1,?)",
                      (n, cat, loc, ward, urg, st, (datetime.now() - timedelta(days=age)).isoformat()))
    d.commit()


def ward_of(place):
    """Stable demo ward (1-9) from the locality name. Still a demo grid, not real ward boundaries."""
    key = (place or "unknown").strip().lower().encode()
    return int(hashlib.sha1(key).hexdigest(), 16) % 9 + 1
