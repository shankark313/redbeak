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

GLOSS_BY_ANCHOR = dict(zip(prompts.ANCHORS, prompts.QUESTION_GLOSSES))


def slug(name):
    return re.sub(r"[^A-Za-z0-9஀-௿]+", "_", name).strip("_") or "child"


def transcribe_answer(
    audio_bytes, ext, question, mode, is_followup, session_id, seq, question_gloss=None
):
    audio_dir = SESSIONS_DIR / session_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"a{seq:02d}.{ext}"
    audio_path.write_bytes(audio_bytes)
    text = voice.stt(audio_bytes, ext=ext)
    return {
        "question": question,
        "question_gloss": question_gloss or GLOSS_BY_ANCHOR.get(question),
        "text": text,
        "gloss": voice.gloss(text) if text else None,
        "mode": mode,
        "is_followup": is_followup,
        "audio_file": str(audio_path),
    }


def build_results(name, age_months, mode, answers, session_id):
    """Segment every answer, compute metrics/verdict/analysis, save, return."""
    utterances = []
    for a in answers:
        if a["text"].strip():
            segs, how = analyst.segment(a["text"])
        else:
            segs, how = [], "empty"
        a["segments"], a["seg_method"] = segs, how
        utterances.extend(segs)

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
        "answers": answers,
        "metrics": m,
        "verdict": v,
        "breakdown": breakdown,
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
