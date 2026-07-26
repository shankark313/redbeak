"""Redbeak — Tamil speech-milestone screening voice agent (Streamlit demo)."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import analyst
import prompts
import store
import voice
from pipeline import (
    GLOSS_BY_ANCHOR,
    SESSIONS_DIR,
    build_results,
    slug,
    transcribe_answer,
)

st.set_page_config(page_title="Redbeak", page_icon="🦜", layout="wide")

CREAM = "#FAF8F5"
INK = "#2E2A26"
ACCENT = "#9B8B7E"

FOOTER = (
    "Screening prompt, not a diagnosis. "
    "A speech-language pathologist assesses language fully."
)

VERDICTS = {
    "tracking_well": ("Tracking well", "#5F8D5F", "#EAF3EA"),
    "keep_watching": ("Keep watching", "#B07D2B", "#F8EEDB"),
    "worth_mentioning": ("Worth mentioning", "#B25E4B", "#F6E4DF"),
    "sample_too_short": ("Sample too short", "#8A857E", "#EEEBE6"),
}

GUIDED = "Guided (standardized)"
CONVERSATIONAL = "Conversational (adaptive)"

PLAN_FRAMING = {
    "tracking_well": "Things are tracking well — here are five little games "
    "to keep stretching those sentences, purely for fun.",
    "keep_watching": "Let's build this together — five little games for the "
    "week, aimed right where they'll help most.",
    "worth_mentioning": "Let's build this together — five little games for "
    "the week, aimed right where they'll help most.",
    "sample_too_short": "While you plan a longer chat, here are five little "
    "games to get more words flowing at home.",
}

PLAN_FOOTER = (
    "Play ideas for home — not therapy. If concerns persist, a "
    "speech-language pathologist can assess fully."
)

# bulbul:v3-compatible speakers only (the v2 roster 400s on this model)
PRACTICE_VOICES = [
    ("shubh", "Shubh — calm male (default)"),
    ("ritu", "Ritu — warm female"),
    ("priya", "Priya — gentle female"),
    ("kavya", "Kavya — bright female"),
    ("rahul", "Rahul — friendly male"),
    ("anand", "Anand — cheerful male"),
]

BUILDING_LABELS = {
    "mlu": "longer phrases",
    "longest": "longer phrases",
    "unique": "new words",
}

AGES = {
    f"{y} years".replace(".5", "½"): int(y * 12)
    for y in (2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6)
}

LIVE_DIR = SESSIONS_DIR / "live"


# ------------------------------------------------------------------ chrome

def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {CREAM}; color: {INK}; }}
        h1, h2, h3, h4, .stMarkdown {{ color: {INK}; }}
        section[data-testid="stSidebar"] {{
            background: #F3EFE9; border-right: 1px solid #E4DDD3;
        }}
        .rb-q {{
            background: #FFFFFF; border: 1px solid #E4DDD3;
            border-left: 5px solid {ACCENT};
            padding: 0.9rem 1.1rem; border-radius: 12px;
            font-size: 1.25rem; margin: 0.4rem 0 0.8rem 0;
        }}
        .rb-a {{
            background: #F1EBE3; padding: 0.7rem 1rem;
            border-radius: 12px; margin: 0.3rem 0;
        }}
        .rb-gloss {{
            color: #8A857E; font-style: italic; font-size: 0.95rem;
            margin: 0.1rem 0 0.6rem 0.4rem;
        }}
        .rb-qgloss {{
            color: #8A857E; font-style: italic; font-size: 1rem;
            margin: -0.4rem 0 0.8rem 0.4rem;
        }}
        .rb-day b {{ font-size: 0.95rem; }}
        .rb-day .say {{ margin: 0.4rem 0 0.1rem 0; }}
        .rb-day .builds {{ color: {ACCENT}; font-size: 0.85rem; margin-top: 0.4rem; }}
        .rb-card {{
            background: #FFFFFF; border: 1px solid #E4DDD3;
            border-radius: 14px; padding: 1rem 1.2rem; height: 100%;
        }}
        .rb-card h4 {{ margin: 0 0 0.5rem 0; color: {ACCENT}; }}
        .rb-metric {{
            background: #FFFFFF; border: 1px solid #E4DDD3;
            border-radius: 14px; padding: 0.8rem 1rem; text-align: center;
        }}
        .rb-metric .v {{ font-size: 1.7rem; font-weight: 700; }}
        .rb-metric .l {{ color: #8A857E; font-size: 0.8rem; }}
        .rb-metric .b {{ color: {ACCENT}; font-size: 0.75rem; }}
        .rb-pill {{
            display: inline-block; padding: 0.45rem 1.2rem;
            border-radius: 999px; font-weight: 700; font-size: 1.05rem;
        }}
        .rb-footer {{
            color: #8A857E; font-size: 0.85rem; border-top: 1px solid #E4DDD3;
            margin-top: 2rem; padding-top: 0.7rem;
        }}
        .rb-memory {{
            background: #EFE9F5; border: 1px solid #DCD2E8;
            border-radius: 10px; padding: 0.6rem 1rem; margin: 0.6rem 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header():
    cols = st.columns([1, 11])
    logo = Path("assets/logo.png")
    with cols[0]:
        if logo.exists():
            st.image(str(logo), width=72)
        else:
            st.markdown("<div style='font-size:3rem'>🦜</div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f"<h1 style='margin-bottom:0'>Redbeak</h1>"
            f"<p style='color:{ACCENT};margin-top:0'>A friendly Tamil chat that "
            f"listens to how your child talks — ages 2 to 6.</p>",
            unsafe_allow_html=True,
        )


def footer():
    st.markdown(f"<div class='rb-footer'>{FOOTER}</div>", unsafe_allow_html=True)


@st.cache_resource
def warm_tts():
    voice.warm_anchors()
    return True


# ------------------------------------------------------------------ pipeline
# (slug / transcribe_answer / build_results live in pipeline.py, shared
# with the hands-free live.py CLI)

_AUDIO_MIME = {"wav": "audio/wav", "m4a": "audio/mp4", "mp3": "audio/mpeg"}


def answer_player(a):
    """Render an inline player for this answer's persisted audio.
    Skips silently if the file is gone — never an API call, never an error."""
    path = a.get("audio_file")
    if not path:
        return
    p = Path(path)
    try:
        data = p.read_bytes() if p.exists() else None
    except Exception:
        data = None
    if data:
        ext = p.suffix.lstrip(".").lower()
        st.audio(data, format=_AUDIO_MIME.get(ext, "audio/wav"))


def run_folder(folder, name, age_months):
    """Non-interactive: a01..a09 audio files straight to results."""
    p = Path(folder).expanduser()
    session_id = time.strftime("%Y%m%d_%H%M%S") + "_" + slug(name)
    answers = []
    for i, q in enumerate(prompts.ANCHORS, 1):
        found = None
        for ext in ("wav", "m4a", "mp3"):
            cand = p / f"a{i:02d}.{ext}"
            if cand.exists():
                found = cand
                break
        if not found:
            continue
        answers.append(
            transcribe_answer(
                found.read_bytes(), found.suffix[1:], q, GUIDED, False,
                session_id, i, question_gloss=prompts.QUESTION_GLOSSES[i - 1],
            )
        )
    if not answers:
        return None
    return build_results(name, age_months, GUIDED, answers, session_id)


# ------------------------------------------------------------------ results UI

def metric_card(col, label, value, band=""):
    col.markdown(
        f"<div class='rb-metric'><div class='v'>{value}</div>"
        f"<div class='l'>{label}</div><div class='b'>{band}</div></div>",
        unsafe_allow_html=True,
    )


def render_results(session):
    m = session["metrics"]
    band = analyst.band_for(session["age_months"])
    label, fg, bg = VERDICTS[session["verdict"]]

    st.subheader(f"Results — {session['child']}, {session['age_months']} months")
    st.markdown(
        f"<span class='rb-pill' style='color:{fg};background:{bg};"
        f"border:1.5px solid {fg}'>{label}</span>",
        unsafe_allow_html=True,
    )

    if session.get("memory"):
        mem = session["memory"]
        st.markdown(
            f"<div class='rb-memory'>🧠 Last session MLU "
            f"<b>{mem['prev_mlu']:.2f}</b> → today <b>{m['mlu']:.2f}</b>"
            f"<span style='color:#8A857E'> · previous session "
            f"{mem['prev_date']}</span></div>",
            unsafe_allow_html=True,
        )

    lo, hi = band["mlu"]
    cols = st.columns(6)
    metric_card(cols[0], "MLU", f"{m['mlu']:.2f}", f"typical {lo}–{hi}")
    metric_card(cols[1], "Longest utterance", int(m["longest"]), f"typical ≥ {band['longest']}")
    metric_card(cols[2], "Unique words", int(m["unique_words"]), f"typical ≥ {band['unique']}*")
    metric_card(cols[3], "Total words", int(m["total_words"]), "≥ 40 to screen")
    metric_card(cols[4], "Utterances", int(m["utterances"]), f"TTR {m['ttr']:.2f}")
    metric_card(cols[5], "Code-mixed words", int(m["code_mixed"]), "Tamil + English")
    st.caption("*unique-word norm applies only to samples of 150+ words")

    st.markdown("#### Metric breakdown")
    st.table(
        [
            {
                "Metric": r["metric"],
                "This session": str(r["value"]),
                "Typical for age": r["typical"],
                "Status": r["status"],
            }
            for r in session["breakdown"]
        ]
    )

    st.markdown("#### What the numbers say")
    st.write(session["analysis"])

    cards = session["cards"]
    c1, c2, c3 = st.columns(3)
    for col, title, key in (
        (c1, "👨‍👩‍👧 Family briefing", "briefing"),
        (c2, "✨ A lovely moment", "lovely_moment"),
        (c3, "🎲 Play idea", "play_idea"),
    ):
        col.markdown(
            f"<div class='rb-card'><h4>{title}</h4>{cards.get(key, '')}</div>",
            unsafe_allow_html=True,
        )

    # DISPLAY tier: what_to_say_ta is for the parent to read aloud — it is
    # generated text and must never be routed to voice.tts
    plan = session.get("play_plan")
    if plan:
        st.markdown("#### 🗓️ This week's play plan")
        st.write(PLAN_FRAMING.get(session["verdict"], PLAN_FRAMING["keep_watching"]))
        pcols = st.columns(5)
        for col, d in zip(pcols, plan):
            col.markdown(
                f"<div class='rb-card rb-day'><h4>{d['day']}</h4>"
                f"<b>{d['activity_name']}</b>"
                f"<div class='say'>🗣️ {d['what_to_say_ta']}</div>"
                f"<div class='rb-gloss'>{d['what_to_say_en']}</div>"
                f"<div class='builds'>Builds: {d['builds']}</div></div>",
                unsafe_allow_html=True,
            )
        st.caption(PLAN_FOOTER)

    with st.expander("Full conversation (Tamil + English)"):
        for a in session["answers"]:
            tag = " · follow-up" if a.get("is_followup") else ""
            st.markdown(f"**🦜 {a['question']}**{tag}")
            q_gloss = a.get("question_gloss") or GLOSS_BY_ANCHOR.get(a["question"])
            if q_gloss:
                st.markdown(f"<div class='rb-gloss'>{q_gloss}</div>", unsafe_allow_html=True)
            if a["text"]:
                st.markdown(f"<div class='rb-a'>{a['text']}</div>", unsafe_allow_html=True)
                if a.get("gloss"):
                    st.markdown(
                        f"<div class='rb-gloss'>{a['gloss']}</div>", unsafe_allow_html=True
                    )
                answer_player(a)
                st.caption(f"segmentation: {a.get('seg_method', '—')}")
            else:
                answer_player(a)
                st.caption("(no words captured)")

    st.download_button(
        "⬇️ Download session JSON",
        data=json.dumps(session, ensure_ascii=False, indent=2),
        file_name=f"redbeak_{session['id']}.json",
        mime="application/json",
    )


# ---------------------------------------------------------- practice & progress

def children_index():
    """name -> list of saved sessions (oldest first), from disk."""
    idx = {}
    for p in sorted(SESSIONS_DIR.glob("*.json")):
        if p.name.startswith("practice_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = (d.get("child") or "").strip()
        if name and d.get("metrics"):
            idx.setdefault(name, []).append(d)
    return idx


def practice_path(name):
    return SESSIONS_DIR / f"practice_{slug(name)}.json"


def load_practice(name):
    try:
        return json.loads(practice_path(name).read_text(encoding="utf-8"))
    except Exception:
        return {"voice": "shubh", "log": []}


def save_practice(name, data):
    SESSIONS_DIR.mkdir(exist_ok=True)
    practice_path(name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    store.save_practice(name, data)


def merged_sessions(name, disk_sessions):
    """Disk sessions + any Supabase-only ones, deduped by id, oldest first."""
    seen = {s.get("id") for s in disk_sessions}
    extra = [s for s in store.child_sessions(name) if s.get("id") not in seen]
    return sorted(disk_sessions + extra, key=lambda s: s.get("timestamp", ""))


def currently_building(latest):
    skills = []
    for row in latest.get("breakdown", []):
        if row["status"] != "⚠":
            continue
        for key, label in BUILDING_LABELS.items():
            if key in row["metric"].lower() and label not in skills:
                skills.append(label)
    return skills


def sidebar_child_picker(idx):
    names = sorted(idx)
    with st.sidebar:
        st.markdown("### Child")
        return st.selectbox("Choose a child", names, key="pp_child")


def scenario_by_id(sid):
    for sc in prompts.SCENARIOS:
        if sc["id"] == sid:
            return sc
    return None


def finish_practice():
    """Same analyst metrics as Session, compact recap, no verdict."""
    ss = st.session_state
    utterances = []
    with st.spinner("Counting the words…"):
        for a in ss.answers:
            if a["text"].strip():
                segs, how = analyst.segment(a["text"])
            else:
                segs, how = [], "empty"
            a["segments"], a["seg_method"] = segs, how
            utterances.extend(segs)
        m = analyst.metrics(utterances)

    # brand-new words vs every previous saved session for this child
    new_words = None
    prev_sessions = children_index().get(ss.live_name, [])
    if prev_sessions:
        seen = set()
        for s in prev_sessions:
            for a in s.get("answers", []):
                seen.update(w.casefold() for w in analyst.words_of(a.get("text", "")))
        today_words = {
            w.casefold() for u in utterances for w in analyst.words_of(u)
        }
        new_words = len(today_words - seen)

    ss.practice_recap = {
        "child": ss.live_name,
        "scenario_id": ss.scenario_id,
        "metrics": m,
        "new_words": new_words,
        "answers": ss.answers,
    }
    prac = load_practice(ss.live_name)
    prac.setdefault("sessions", []).append(
        {
            "date": date.today().isoformat(),
            "scenario_id": ss.scenario_id,
            "mlu": m["mlu"],
            "total_words": m["total_words"],
            "unique_words": m["unique_words"],
        }
    )
    save_practice(ss.live_name, prac)
    ss.phase = "practice_done"


def render_practice_recap():
    r = st.session_state.practice_recap
    m = r["metrics"]
    sc = scenario_by_id(r["scenario_id"])
    title = f"{sc['emoji']} {sc['title_en']}" if sc else "Practice"
    st.subheader(f"{title} — nice chatting, {r['child']}!")

    cols = st.columns(3)
    metric_card(cols[0], "MLU today", f"{m['mlu']:.2f}")
    metric_card(cols[1], "Words today", int(m["total_words"]))
    if r["new_words"] is not None:
        metric_card(cols[2], "Brand-new words", int(r["new_words"]),
                    "vs earlier sessions")
    else:
        metric_card(cols[2], "Different words", int(m["unique_words"]))

    warm = (
        f"That was {m['total_words']} words of chatting today"
        + (f" — including {r['new_words']} we'd never heard before!"
           if r["new_words"] else "!")
        + " Same time tomorrow?"
    )
    st.markdown(f"<div class='rb-memory'>💛 {warm}</div>", unsafe_allow_html=True)

    with st.expander("Today's conversation"):
        for a in r["answers"]:
            tag = " · follow-up" if a.get("is_followup") else ""
            st.markdown(f"**🦜 {a['question']}**{tag}")
            if a.get("question_gloss"):
                st.markdown(f"<div class='rb-gloss'>{a['question_gloss']}</div>",
                            unsafe_allow_html=True)
            if a["text"]:
                st.markdown(f"<div class='rb-a'>{a['text']}</div>",
                            unsafe_allow_html=True)
                if a.get("gloss"):
                    st.markdown(f"<div class='rb-gloss'>{a['gloss']}</div>",
                                unsafe_allow_html=True)
            answer_player(a)

    if st.button("🧸 Another practice chat"):
        st.session_state.phase = "setup"
        st.session_state.practice_recap = None
        st.rerun()
    st.caption("Play ideas for home — not therapy.")


def render_practice():
    ss = st.session_state
    idx = children_index()
    if not idx:
        st.info("No saved sessions yet — run a Session first, then practise "
                "here with themed chats.")
        return

    child = sidebar_child_picker(idx)
    prac = load_practice(child)
    voice_ids = [v[0] for v in PRACTICE_VOICES]
    voice_labels = [v[1] for v in PRACTICE_VOICES]
    current = prac.get("voice", "shubh")
    with st.sidebar:
        chosen_label = st.selectbox(
            "Practice voice",
            voice_labels,
            index=voice_ids.index(current) if current in voice_ids else 0,
            key="pp_voice",
        )
    chosen = voice_ids[voice_labels.index(chosen_label)]
    if chosen != current:
        prac["voice"] = chosen
        save_practice(child, prac)

    if ss.phase == "chat" and ss.kind == "practice":
        render_chat()
        return
    if ss.phase == "practice_done" and ss.practice_recap:
        render_practice_recap()
        return

    st.subheader(f"Practice with {child}")

    # Mon–Fri day strip, today highlighted; practised days get a flame
    prac_dates = {e.get("date") for e in prac.get("sessions", [])}
    monday = date.today() - timedelta(days=date.today().weekday())
    chips = []
    for i, dname in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri")):
        d = monday + timedelta(days=i)
        is_today = d == date.today()
        done = d.isoformat() in prac_dates
        style = (
            f"background:{ACCENT};color:#fff;" if is_today
            else "background:#EFEBE4;color:#8A857E;"
        )
        chips.append(
            f"<span class='rb-pill' style='{style}font-size:0.85rem;"
            f"padding:0.3rem 0.9rem'>{dname}{' 🔥' if done else ''}</span>"
        )
    st.markdown(" ".join(chips), unsafe_allow_html=True)
    st.write("Pick today's scene — a five-minute chat, all play.")

    cols = st.columns(len(prompts.SCENARIOS))
    for col, sc in zip(cols, prompts.SCENARIOS):
        selected = ss.pp_pick == sc["id"]
        border = f"2px solid {ACCENT}" if selected else "1px solid #E4DDD3"
        col.markdown(
            f"<div class='rb-card' style='text-align:center;border:{border}'>"
            f"<div style='font-size:2rem'>{sc['emoji']}</div>"
            f"<b>{sc['title_ta']}</b>"
            f"<div class='rb-gloss' style='margin:0'>{sc['title_en']}</div></div>",
            unsafe_allow_html=True,
        )
        if col.button("Choose", key=f"pick_{sc['id']}", width="stretch"):
            ss.pp_pick = sc["id"]
            st.rerun()

    picked = scenario_by_id(ss.pp_pick)
    if st.button(
        "▶ Start practice chat", type="primary", disabled=picked is None,
    ):
        latest = idx[child][-1]
        start_session(
            child, latest["age_months"], CONVERSATIONAL,
            kind="practice", q_list=list(picked["prompts"]),
            scenario_id=picked["id"], tts_voice=prac.get("voice", "shubh"),
        )
        st.rerun()
    st.caption("Play ideas for home — not therapy.")


def render_progress():
    idx = children_index()
    if not idx:
        st.info("No saved sessions yet — after your first session, this page "
                "shows how the numbers grow over time.")
        return
    child = sidebar_child_picker(idx)
    sessions = merged_sessions(child, idx[child])
    if not sessions:
        st.info("No sessions for this child yet.")
        return

    st.subheader(f"Progress — {child}")
    rows = [
        {
            "date": (s.get("timestamp") or "")[:16],
            "MLU": s["metrics"]["mlu"],
            "Unique words": s["metrics"]["unique_words"],
            "verdict": s.get("verdict", ""),
        }
        for s in sessions
    ]
    import altair as alt
    import pandas as pd

    prac = load_practice(child)
    prac_rows = [
        {"date": e["date"], "MLU": e["mlu"]}
        for e in prac.get("sessions", [])
        if e.get("mlu") is not None
    ]

    df_s = pd.DataFrame(rows)
    c1, c2 = st.columns(2)
    c1.markdown("**MLU across sessions** · ○ practice chats")
    mlu_line = (
        alt.Chart(df_s)
        .mark_line(point=True, color=ACCENT, strokeWidth=2.5)
        .encode(x=alt.X("date:N", title=None), y=alt.Y("MLU:Q", title="MLU"))
    )
    layers = mlu_line
    if prac_rows:
        dots = (
            alt.Chart(pd.DataFrame(prac_rows))
            .mark_circle(color="#CBBFB1", size=110, opacity=0.8)
            .encode(x="date:N", y="MLU:Q")
        )
        layers = mlu_line + dots
    c1.altair_chart(layers.properties(height=220), width="stretch")

    c2.markdown("**Unique words across sessions**")
    uniq_line = (
        alt.Chart(df_s)
        .mark_line(point=True, color="#5F8D5F", strokeWidth=2.5)
        .encode(x=alt.X("date:N", title=None),
                y=alt.Y("Unique words:Q", title="unique words"))
    )
    c2.altair_chart(uniq_line.properties(height=220), width="stretch")

    pills = []
    for r in rows:
        label, fg, bg = VERDICTS.get(r["verdict"], VERDICTS["sample_too_short"])
        pills.append(
            f"<span class='rb-pill' style='color:{fg};background:{bg};"
            f"border:1px solid {fg};font-size:0.8rem;padding:0.2rem 0.7rem'>"
            f"{r['date']} · {label}</span>"
        )
    st.markdown(" ".join(pills), unsafe_allow_html=True)

    week_ago = date.today() - timedelta(days=6)
    days = {
        e["date"]
        for e in prac.get("log", []) + prac.get("sessions", [])
        if e.get("date", "") >= week_ago.isoformat()
    }
    st.markdown(
        f"<div class='rb-memory'>🔥 <b>{len(days)}</b> practice day"
        f"{'s' if len(days) != 1 else ''} this week</div>",
        unsafe_allow_html=True,
    )
    skills = currently_building(sessions[-1])
    if skills:
        st.markdown(f"**Currently building:** {', '.join(skills)}")
    else:
        st.markdown("**Currently building:** keep enjoying — all bands met 🎉")


# ------------------------------------------------------------------ live page

def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


@st.fragment(run_every=1.0)
def live_feed_fragment():
    """Polls the live.py feed once a second and renders it as chat bubbles."""
    ss = st.session_state
    d = ss.get("live_dir")
    if not d:
        st.caption("No live session yet — set it up in the sidebar and press "
                   "▶ Start.")
        return
    dpath = Path(d)
    meta, events = {}, []
    try:
        meta = json.loads((dpath / "feed_meta.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        for line in (dpath / "feed.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass

    for e in events:
        if e["kind"] in ("prompt", "followup"):
            tag = " 💬" if e["kind"] == "followup" else ""
            st.markdown(f"<div class='rb-q'>🦜 {e['ta']}{tag}</div>",
                        unsafe_allow_html=True)
            if e.get("en"):
                st.markdown(f"<div class='rb-qgloss'>{e['en']}</div>",
                            unsafe_allow_html=True)
        else:
            if e.get("ta"):
                st.markdown(f"<div class='rb-a'>🧒 {e['ta']}</div>",
                            unsafe_allow_html=True)
                if e.get("en"):
                    st.markdown(f"<div class='rb-gloss'>{e['en']}</div>",
                                unsafe_allow_html=True)
            else:
                st.caption("🧒 (no words captured)")
            answer_player({"audio_file": e.get("audio_path")})

    if meta.get("status") == "finished":
        if meta.get("metrics"):
            m = meta["metrics"]
            label, fg, bg = VERDICTS.get(meta.get("verdict", ""),
                                         VERDICTS["sample_too_short"])
            st.markdown(
                f"<span class='rb-pill' style='color:{fg};background:{bg};"
                f"border:1.5px solid {fg}'>{label}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"**MLU {m['mlu']:.2f}** · longest {m['longest']} · "
                f"{m['total_words']} words ({m['unique_words']} unique) · "
                f"{m['utterances']} utterances"
            )
        st.info("Session finished — open **Past sessions** on the Session "
                "page for the full results, cards and play plan.")
    elif not _pid_alive(ss.get("live_pid")):
        if events:
            st.caption("session ended")
    else:
        st.caption("🔴 live — listening…")


def render_live():
    ss = st.session_state
    alive = _pid_alive(ss.get("live_pid"))

    with st.sidebar:
        st.markdown("### Live setup")
        name = st.text_input("Child's name", key="lv_name")
        age_label = st.selectbox("Age", list(AGES.keys()), index=4, key="lv_age")
        scen_labels = ["Screening anchors (9 questions)"] + [
            f"{s['emoji']} {s['title_en']}" for s in prompts.SCENARIOS
        ]
        scen_pick = st.selectbox("Conversation", scen_labels, key="lv_scen")

    st.subheader("🔴 Live — hands-free conversation")
    c1, c2 = st.columns([1, 1])
    if c1.button("▶ Start live session", type="primary",
                 disabled=alive or not name.strip()):
        sid = f"live_{time.strftime('%Y%m%d_%H%M%S')}_{slug(name.strip())}"
        cmd = [sys.executable, "live.py", "--name", name.strip(),
               "--age", str(AGES[age_label]), "--session-id", sid]
        idx = scen_labels.index(scen_pick)
        if idx == 0:
            cmd.append("--anchors")
        else:
            cmd += ["--scenario", prompts.SCENARIOS[idx - 1]["id"]]
        feed_dir = LIVE_DIR / sid
        feed_dir.mkdir(parents=True, exist_ok=True)
        log = open(feed_dir / "stdout.log", "w")
        proc = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
        ss.live_pid = proc.pid
        ss.live_dir = str(feed_dir)
        st.rerun()
    if c2.button("■ Stop", disabled=not alive):
        try:
            os.kill(ss.live_pid, signal.SIGINT)  # live.py's Ctrl+C path saves
        except Exception:
            pass

    live_feed_fragment()


# ------------------------------------------------------------------ session flow

def init_state():
    ss = st.session_state
    ss.setdefault("phase", "setup")
    ss.setdefault("answers", [])
    ss.setdefault("anchor_idx", 0)
    ss.setdefault("awaiting", "anchor")
    ss.setdefault("followup_q", None)
    ss.setdefault("followup_gloss", None)
    ss.setdefault("session_id", "")
    ss.setdefault("results", None)
    ss.setdefault("live_name", "")
    ss.setdefault("live_age", 48)
    ss.setdefault("live_mode", GUIDED)
    ss.setdefault("kind", "screen")
    ss.setdefault("q_list", None)
    ss.setdefault("scenario_id", None)
    ss.setdefault("tts_voice", "shubh")
    ss.setdefault("pp_pick", None)
    ss.setdefault("practice_recap", None)
    ss.setdefault("live_pid", None)
    ss.setdefault("live_dir", None)


def start_session(name, age_months, mode, kind="screen", q_list=None,
                  scenario_id=None, tts_voice="shubh"):
    ss = st.session_state
    ss.phase = "chat"
    ss.answers = []
    ss.anchor_idx = 0
    ss.awaiting = "anchor"
    ss.followup_q = None
    ss.followup_gloss = None
    ss.live_name = name
    ss.live_age = age_months
    ss.live_mode = mode
    ss.kind = kind
    ss.q_list = q_list or [
        {"ta": q, "en": g}
        for q, g in zip(prompts.ANCHORS, prompts.QUESTION_GLOSSES)
    ]
    ss.scenario_id = scenario_id
    ss.tts_voice = tts_voice
    prefix = "prax" if kind == "practice" else "scr"
    ss.session_id = f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{slug(name)}"


def finish_session():
    ss = st.session_state
    if ss.kind == "practice":
        finish_practice()
        return
    with st.spinner("Crunching the numbers…"):
        ss.results = build_results(
            ss.live_name, ss.live_age, ss.live_mode, ss.answers, ss.session_id
        )
    ss.phase = "results"


def handle_answer(audio_bytes, ext):
    ss = st.session_state
    is_followup = ss.awaiting == "followup"
    if is_followup:
        question, q_gloss = ss.followup_q, ss.get("followup_gloss")
    else:
        entry = ss.q_list[ss.anchor_idx]
        question, q_gloss = entry["ta"], entry["en"]
    with st.spinner("Listening…"):
        ans = transcribe_answer(
            audio_bytes, ext, question, ss.live_mode, is_followup,
            ss.session_id, len(ss.answers) + 1, question_gloss=q_gloss,
        )
    ss.answers.append(ans)

    if (
        not is_followup
        and ss.live_mode == CONVERSATIONAL
        and ans["text"].strip()
    ):
        fu = voice.followup(ans["text"], ss.live_age)
        if fu:
            ss.followup_q = fu
            # spoken-line guarantee: the bubble always carries an English
            # gloss — generic placeholder if translate degrades
            ss.followup_gloss = (
                voice.gloss(fu) or "(asking a little more about what they said)"
            )
            ss.awaiting = "followup"
            return
    ss.followup_q = None
    ss.followup_gloss = None
    ss.awaiting = "anchor"
    ss.anchor_idx += 1
    if ss.anchor_idx >= len(ss.q_list):
        finish_session()


def render_chat():
    ss = st.session_state
    n = len(ss.q_list)
    is_followup = ss.awaiting == "followup"
    question = ss.followup_q if is_followup else ss.q_list[ss.anchor_idx]["ta"]

    done_anchors = ss.anchor_idx
    st.progress(done_anchors / n)
    st.caption(
        f"Question {min(done_anchors + 1, n)} of {n}"
        + (" · follow-up 💬" if is_followup else "")
    )

    # SPOKEN tier: question is either a hand-written prompts.py line or a
    # follow-up that passed clean() — never raw model output
    audio = voice.tts(question, speaker=ss.tts_voice)
    if audio:
        st.audio(audio, format="audio/wav")
    st.markdown(f"<div class='rb-q'>🦜 {question}</div>", unsafe_allow_html=True)
    q_gloss = (
        ss.get("followup_gloss") if is_followup
        else ss.q_list[ss.anchor_idx]["en"]
    )
    if q_gloss:
        st.markdown(f"<div class='rb-qgloss'>{q_gloss}</div>", unsafe_allow_html=True)

    step = f"{ss.anchor_idx}_{ss.awaiting}_{len(ss.answers)}"
    mic = st.audio_input("🎙️ Record the answer", key=f"mic_{step}")
    up = st.file_uploader(
        "…or upload a recording (wav / m4a)", type=["wav", "m4a"], key=f"up_{step}"
    )

    got = mic or up
    if got is not None:
        ext = "wav"
        if up is not None and mic is None:
            ext = Path(up.name).suffix.lstrip(".").lower() or "wav"
        handle_answer(got.getvalue(), ext)
        st.rerun()

    if ss.answers:
        st.caption("▶️ Last answer")
        answer_player(ss.answers[-1])

    if ss.answers:
        with st.expander("So far…", expanded=False):
            for a in ss.answers:
                tag = " 💬" if a["is_followup"] else ""
                st.markdown(f"**🦜 {a['question']}**{tag}")
                q_gloss = a.get("question_gloss") or GLOSS_BY_ANCHOR.get(a["question"])
                if q_gloss:
                    st.markdown(
                        f"<div class='rb-gloss'>{q_gloss}</div>", unsafe_allow_html=True
                    )
                if a["text"]:
                    st.markdown(f"<div class='rb-a'>{a['text']}</div>", unsafe_allow_html=True)
                    if a.get("gloss"):
                        st.markdown(
                            f"<div class='rb-gloss'>{a['gloss']}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("(no words captured)")
                answer_player(a)

    st.divider()
    if st.button("🏁 Finish early — show results", disabled=not ss.answers):
        finish_session()
        st.rerun()


# ------------------------------------------------------------------ main

def main():
    inject_css()
    init_state()
    header()
    warm_tts()
    ss = st.session_state

    with st.sidebar:
        page = st.radio(
            "Page", ["🎤 Session", "🔴 Live", "🧸 Practice", "📈 Progress"],
            key="page", label_visibility="collapsed",
        )
        st.divider()

    if page == "🔴 Live":
        render_live()
        footer()
        return
    if page == "🧸 Practice":
        render_practice()
        footer()
        return
    if page == "📈 Progress":
        render_progress()
        footer()
        return

    with st.sidebar:
        st.markdown("### Session setup")
        name = st.text_input("Child's name", value=ss.live_name or "")
        age_label = st.selectbox("Age", list(AGES.keys()), index=4)
        mode = st.radio("Mode", [GUIDED, CONVERSATIONAL])

        if ss.phase == "chat" and ss.kind == "screen":
            st.info("Session in progress…")
        elif st.button("▶️ Start session", type="primary", disabled=not name.strip()):
            start_session(name.strip(), AGES[age_label], mode)
            st.rerun()

        st.divider()
        st.markdown("### Past sessions")
        saved = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)
        pick = st.selectbox(
            "Re-render a saved session (no API calls)",
            ["—"] + [p.stem for p in saved],
        )

        st.divider()
        st.markdown("### Load answers from folder")
        folder = st.text_input("Folder containing a01..a09 audio files")
        if st.button("Run folder → results", disabled=not (folder and name.strip())):
            with st.spinner("Transcribing and analysing…"):
                result = run_folder(folder, name.strip(), AGES[age_label])
            if result:
                ss.results = result
                ss.phase = "results"
                st.rerun()
            else:
                st.warning("No a01..a09 audio files found there.")

    if pick != "—":
        data = json.loads((SESSIONS_DIR / f"{pick}.json").read_text(encoding="utf-8"))
        render_results(data)
        footer()
        return

    if ss.phase == "chat" and ss.kind == "screen":
        render_chat()
    elif ss.phase == "results" and ss.results:
        render_results(ss.results)
        if st.button("🔄 New session"):
            ss.phase = "setup"
            ss.results = None
            st.rerun()
    else:
        st.markdown(
            "Pick a name, an age and a mode in the sidebar, then press "
            "**Start session**. Redbeak asks 9 friendly questions in Tamil, "
            "listens, and shows you what the numbers say."
        )

    footer()


main()
