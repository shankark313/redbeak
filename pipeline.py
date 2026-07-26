"""Shared session pipeline — used by the Streamlit app and live.py.

No Streamlit imports here: everything is plain disk + Sarvam + Supabase, so
the hands-free CLI can produce sessions in exactly the app's format.
"""

import json
import re
import time
from pathlib import Path

import analyst
import prompts
import store
import voice

SESSIONS_DIR = Path("sessions")

GLOSS_BY_ANCHOR = {}
for _pack in prompts.LANGS.values():
    GLOSS_BY_ANCHOR.update(zip(_pack["anchors"], _pack["glosses"]))


def slug(name):
    return re.sub(r"[^A-Za-z0-9஀-௿]+", "_", name).strip("_") or "child"


def transcribe_answer(
    audio_bytes, ext, question, mode, is_followup, session_id, seq,
    question_gloss=None, lang="ta-IN",
):
    audio_dir = SESSIONS_DIR / session_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"a{seq:02d}.{ext}"
    audio_path.write_bytes(audio_bytes)
    text = voice.stt(audio_bytes, ext=ext, lang=lang)
    return {
        "question": question,
        "question_gloss": question_gloss or GLOSS_BY_ANCHOR.get(question),
        "text": text,
        "gloss": voice.gloss(text, lang=lang) if text else None,
        "mode": mode,
        "is_followup": is_followup,
        "audio_file": str(audio_path),
    }


def _segment_all(answers):
    utterances = []
    for a in answers:
        if a["text"].strip():
            segs, how = analyst.segment(a["text"])
        else:
            segs, how = [], "empty"
        a["segments"], a["seg_method"] = segs, how
        utterances.extend(segs)
    return utterances


def build_results(name, age_months, mode, answers, session_id, lang="ta-IN"):
    """Segment every answer, compute metrics/verdict/analysis, save, return."""
    utterances = _segment_all(answers)
    m = analyst.metrics(utterances)
    v = analyst.verdict(m, age_months)
    breakdown = analyst.metric_breakdown(m, age_months)

    prev = store.previous_session(name)  # look up BEFORE saving today's
    memory = None
    if prev and prev.get("metrics", {}).get("mlu") is not None:
        memory = {
            "prev_mlu": prev["metrics"]["mlu"],
            "prev_date": prev.get("timestamp", ""),
        }

    session = {
        "id": session_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "child": name,
        "age_months": age_months,
        "mode": mode,
        "language": lang,
        "answers": answers,
        "metrics": m,
        "verdict": v,
        "breakdown": breakdown,
        "summary": analyst.summary(m, age_months, v, breakdown),
        "analysis": analyst.analysis(m, age_months, v, breakdown),
        "cards": analyst.card(answers, m, age_months, v, breakdown, name),
        "play_plan": analyst.play_plan(m, age_months, v, breakdown),
        "memory": memory,
    }

    SESSIONS_DIR.mkdir(exist_ok=True)
    path = SESSIONS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{slug(name)}.json"
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    store.upsert_child(name, age_months)
    store.insert_session(session)
    return session


# --------------------------------------------------------------- practice side

def practice_path(name):
    return SESSIONS_DIR / f"practice_{slug(name)}.json"


def load_practice(name):
    try:
        return json.loads(practice_path(name).read_text(encoding="utf-8"))
    except Exception:
        return {"voice": "shubh", "log": []}


def save_practice(name, data):
    data["name"] = name  # practice files are slug-named; keep the real name
    SESSIONS_DIR.mkdir(exist_ok=True)
    practice_path(name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    store.save_practice(name, data)


def child_history_words(name):
    """Every word this child has said across all saved sessions (screening
    and practice) — call BEFORE saving today's session."""
    words = set()
    for p in SESSIONS_DIR.glob("*.json"):
        if p.name.startswith("practice_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (d.get("child") or "").strip().casefold() != name.strip().casefold():
            continue
        for a in d.get("answers", []):
            words.update(w.casefold() for w in analyst.words_of(a.get("text", "")))
    return words


def build_practice_results(name, age_months, answers, session_id, scenario_id,
                           lang="ta-IN"):
    """Practice finish: same analyst metrics, NO verdict, NO screening
    language. Saves a kind:'practice' session JSON, appends the practice
    log entry, returns the session dict (with recap fields)."""
    utterances = _segment_all(answers)
    m = analyst.metrics(utterances)
    breakdown = analyst.metric_breakdown(m, age_months)

    history = child_history_words(name)  # before saving today's
    today_words = {w.casefold() for u in utterances for w in analyst.words_of(u)}
    new_words = len(today_words - history) if history else None

    warm = (
        f"That was {m['total_words']} words of chatting today"
        + (f" — including {new_words} we'd never heard before!"
           if new_words else "!")
        + " Same time tomorrow?"
    )

    session = {
        "id": session_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "child": name,
        "age_months": age_months,
        "mode": "Practice (hands-free)",
        "kind": "practice",
        "language": lang,
        "scenario_id": scenario_id,
        "answers": answers,
        "metrics": m,
        "breakdown": breakdown,
        "new_words": new_words,
        "warm": warm,
    }
    SESSIONS_DIR.mkdir(exist_ok=True)
    path = SESSIONS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{slug(name)}.json"
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    prac = load_practice(name)
    prac.setdefault("sessions", []).append(
        {
            "date": time.strftime("%Y-%m-%d"),
            "scenario_id": scenario_id,
            "mlu": m["mlu"],
            "total_words": m["total_words"],
            "unique_words": m["unique_words"],
        }
    )
    save_practice(name, prac)
    return session
