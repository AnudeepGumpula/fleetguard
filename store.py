"""Audit log + approval queue, stored in SQLite.

Every guard decision is recorded. "ask" decisions also become pending
approvals that a human can approve or deny.
"""
import json, os, sqlite3, time, uuid
from contextlib import contextmanager

DB_PATH = os.environ.get("FLEETGUARD_DB", "fleetguard.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    ticket TEXT NOT NULL,
    requester_role TEXT,
    devices_affected INTEGER,
    decision TEXT NOT NULL,
    reason TEXT,
    signals TEXT,
    latency_ms INTEGER,
    status TEXT NOT NULL,          -- allowed | blocked | pending | approved | denied
    reviewer TEXT,
    reviewed_at REAL,
    review_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON decisions(status);
"""

SIGNAL_KEYS = ("action_class", "severity", "matches_ticket", "injection", "action_confidence")
INITIAL_STATUS = {"allow": "allowed", "block": "blocked", "ask": "pending"}


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with _conn() as c:
        c.executescript(SCHEMA)


def record(call, result):
    rid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute(
            "INSERT INTO decisions (id, created_at, tool, args, ticket, requester_role, devices_affected,"
            " decision, reason, signals, latency_ms, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, time.time(), call["tool"], json.dumps(call.get("args", {})), call["ticket"],
             call.get("requester_role"), call.get("devices_affected"), result["decision"],
             result["reason"], json.dumps({k: result.get(k) for k in SIGNAL_KEYS}),
             result.get("latency_ms"), INITIAL_STATUS[result["decision"]]),
        )
    return rid


def _row(r):
    d = dict(r)
    d["args"] = json.loads(d["args"])
    d["signals"] = json.loads(d["signals"] or "{}")
    return d


def get(rid):
    with _conn() as c:
        r = c.execute("SELECT * FROM decisions WHERE id=?", (rid,)).fetchone()
    return _row(r) if r else None


def list_decisions(status=None, limit=50):
    q, p = "SELECT * FROM decisions", []
    if status:
        q += " WHERE status=?"
        p.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    p.append(limit)
    with _conn() as c:
        return [_row(r) for r in c.execute(q, p).fetchall()]


def review(rid, approve, reviewer, note=""):
    """Approve or deny a pending decision. Returns the updated row, or None if not pending."""
    with _conn() as c:
        cur = c.execute(
            "UPDATE decisions SET status=?, reviewer=?, reviewed_at=?, review_note=?"
            " WHERE id=? AND status='pending'",
            ("approved" if approve else "denied", reviewer, time.time(), note, rid),
        )
        if cur.rowcount == 0:
            return None
    return get(rid)
