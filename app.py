"""Redbeak — Tamil speech-milestone screening voice agent (Streamlit demo)."""

import json
import re
import time
from pathlib import Path

import streamlit as st

import analyst
import prompts
import store
import voice

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

SESSIONS_DIR = Path("sessions")

GLOSS_BY_ANCHOR = dict(zip(prompts.ANCHORS, prompts.QUESTION_GLOSSES))

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

def slug(name):
    return re.sub(r"[^A-Za-z0-9஀-௿]+", "_", name).strip("_") or "child"


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


def start_session(name, age_months, mode):
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
    ss.session_id = time.strftime("%Y%m%d_%H%M%S") + "_" + slug(name)


def finish_session():
    ss = st.session_state
    with st.spinner("Crunching the numbers…"):
        ss.results = build_results(
            ss.live_name, ss.live_age, ss.live_mode, ss.answers, ss.session_id
        )
    ss.phase = "results"


def handle_answer(audio_bytes, ext):
    ss = st.session_state
    is_followup = ss.awaiting == "followup"
    question = ss.followup_q if is_followup else prompts.ANCHORS[ss.anchor_idx]
    q_gloss = ss.get("followup_gloss") if is_followup else None
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
            ss.followup_gloss = voice.gloss(fu)  # same retry/degrade path
            ss.awaiting = "followup"
            return
    ss.followup_q = None
    ss.followup_gloss = None
    ss.awaiting = "anchor"
    ss.anchor_idx += 1
    if ss.anchor_idx >= len(prompts.ANCHORS):
        finish_session()


def render_chat():
    ss = st.session_state
    is_followup = ss.awaiting == "followup"
    question = ss.followup_q if is_followup else prompts.ANCHORS[ss.anchor_idx]

    done_anchors = ss.anchor_idx
    st.progress(done_anchors / len(prompts.ANCHORS))
    st.caption(
        f"Question {min(done_anchors + 1, 9)} of {len(prompts.ANCHORS)}"
        + (" · follow-up 💬" if is_followup else "")
    )

    audio = voice.tts(question)
    if audio:
        st.audio(audio, format="audio/wav")
    st.markdown(f"<div class='rb-q'>🦜 {question}</div>", unsafe_allow_html=True)
    q_gloss = (
        ss.get("followup_gloss") if is_followup
        else prompts.QUESTION_GLOSSES[ss.anchor_idx]
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
        st.markdown("### Session setup")
        name = st.text_input("Child's name", value=ss.live_name or "")
        ages = {f"{y} years".replace(".5", "½"): int(y * 12) for y in
                (2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6)}
        age_label = st.selectbox("Age", list(ages.keys()), index=4)
        mode = st.radio("Mode", [GUIDED, CONVERSATIONAL])

        if ss.phase == "chat":
            st.info("Session in progress…")
        elif st.button("▶️ Start session", type="primary", disabled=not name.strip()):
            start_session(name.strip(), ages[age_label], mode)
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
                result = run_folder(folder, name.strip(), ages[age_label])
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

    if ss.phase == "setup":
        st.markdown(
            "Pick a name, an age and a mode in the sidebar, then press "
            "**Start session**. Redbeak asks 9 friendly questions in Tamil, "
            "listens, and shows you what the numbers say."
        )
    elif ss.phase == "chat":
        render_chat()
    elif ss.phase == "results" and ss.results:
        render_results(ss.results)
        if st.button("🔄 New session"):
            ss.phase = "setup"
            ss.results = None
            st.rerun()

    footer()


main()
