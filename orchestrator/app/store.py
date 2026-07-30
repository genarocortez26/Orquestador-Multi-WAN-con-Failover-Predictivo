"""Persistencia de eventos y decisiones en SQLite.

Se usa sqlite3 de la biblioteca estándar en lugar de SQLAlchemy: para dos tablas
y consultas simples, un ORM agrega dependencia y complejidad sin beneficio.
"""
import os
import sqlite3
import threading
import time

_lock = threading.Lock()
_DB = os.environ.get("DB_PATH", "/data/orchestrator.db")


def _conn():
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            type TEXT NOT NULL,          -- failover | recovery | degraded | predicted | info
            wan_id TEXT,
            detail TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS flow_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            flow TEXT NOT NULL,          -- proto:src:sport->dst:dport
            traffic_class TEXT NOT NULL,
            wan_id TEXT NOT NULL,
            reason TEXT
        )""")


def add_event(etype: str, wan_id: str | None, detail: str):
    with _lock, _conn() as c:
        c.execute("INSERT INTO events (ts, type, wan_id, detail) VALUES (?,?,?,?)",
                  (time.time(), etype, wan_id, detail))


def add_decision(flow: str, tclass: str, wan_id: str, reason: str):
    with _lock, _conn() as c:
        c.execute("INSERT INTO flow_decisions (ts, flow, traffic_class, wan_id, reason) VALUES (?,?,?,?,?)",
                  (time.time(), flow, tclass, wan_id, reason))


def recent_events(limit: int = 100) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def recent_decisions(limit: int = 100) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM flow_decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
