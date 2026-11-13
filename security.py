"""Small helpers: rate limiting, auth decorators, password rules."""
import time
from collections import defaultdict, deque
from functools import wraps
from flask import jsonify, request, session
from db import get_db

_hits = defaultdict(deque)


def rate_limit(limit, per=60):
    """In-memory per-IP limiter (per process). Use Flask-Limiter + Redis when running several workers."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            key = (fn.__name__, request.remote_addr)
            now, q = time.time(), _hits[key]
            while q and now - q[0] > per:
                q.popleft()
            if len(q) >= limit:
                return jsonify(error="Too many requests. Please wait a minute."), 429
            q.append(now)
            return fn(*a, **kw)
        return wrapper
    return deco


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def require(role=None, verified=False):
    """role: None (any logged-in user), 'official' (verified official or admin), 'admin'."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if request.method != "GET" and not request.is_json:
                return jsonify(error="JSON body required."), 415
            u = current_user()
            if not u:
                return jsonify(error="Please log in."), 401
            if role == "admin" and u["role"] != "admin":
                return jsonify(error="Admins only."), 403
            if role == "official" and not (u["role"] == "admin" or (u["role"] == "official" and u["verified"])):
                return jsonify(error="Verified officials only."), 403
            if verified and not u["verified"]:
                return jsonify(error="Verify your account first."), 403
            return fn(u, *a, **kw)
        return wrapper
    return deco
