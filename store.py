"""Supabase write-back for Redbeak sessions.

If SUPABASE_URL / SUPABASE_KEY are absent (or any call fails) everything
no-ops gracefully — the app keeps working from local disk. previous_session()
additionally falls back to scanning sessions/*.json so the memory feature
works in a purely local demo.
"""

import json
import os
from pathlib import Path

SESSIONS_DIR = Path("sessions")

_client = None
_tried = False


def _sb():
    global _client, _tried
    if _tried:
        return _client
    _tried = True
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client

        _client = create_client(url, key)
    except Exception:
        _client = None
    return _client


def upsert_child(name, age_months):
    sb = _sb()
    if not sb or not name:
        return
    try:
        sb.table("children").upsert(
            {"name": name, "age_months": age_months}, on_conflict="name"
        ).execute()
    except Exception:
        pass


def insert_session(session):
    """session: the full session dict app.py builds (child, metrics, verdict...)."""
    sb = _sb()
    if not sb:
        return
    try:
        sb.table("sessions").insert(
            {
                "child_name": session.get("child", ""),
                "age_months": session.get("age_months"),
                "mode": session.get("mode"),
                "verdict": session.get("verdict"),
                "mlu": session.get("metrics", {}).get("mlu"),
                "total_words": session.get("metrics", {}).get("total_words"),
                "created_at": session.get("timestamp"),
                "payload": json.dumps(session, ensure_ascii=False),
            }
        ).execute()
    except Exception:
        pass


def _previous_from_disk(child_name):
    if not SESSIONS_DIR.is_dir():
        return None
    best = None
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("child", "").strip().casefold() == child_name.strip().casefold():
            if best is None:  # newest first thanks to sorted(reverse=True)
                best = data
                break
    return best


def previous_session(child_name):
    """Most recent saved session for this child, for the memory feature
    ('Last session MLU X -> today Y'). Supabase first, disk fallback."""
    if not child_name or not child_name.strip():
        return None
    sb = _sb()
    if sb:
        try:
            res = (
                sb.table("sessions")
                .select("payload")
                .eq("child_name", child_name)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                return json.loads(res.data[0]["payload"])
        except Exception:
            pass
    return _previous_from_disk(child_name)
