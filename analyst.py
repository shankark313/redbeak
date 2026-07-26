"""Segmentation, metrics, norms verdict and family-facing text for Redbeak.

Guardrails live in code, not prompts: the paediatrician sentence is appended
iff verdict == worth_mentioning and stripped otherwise; condition names are
stripped; unknown pronouns become they/them.
"""

import json
import re

import prompts
import voice

# ---------------------------------------------------------------- segmentation

_PUNCT = ".,!?;:\"'“”‘’()[]{}…–—-"


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _llm_parts(text, strict):
    system = prompts.SEGMENT_STRICT if strict else prompts.SEGMENT_SYSTEM
    raw = voice.chat(system, text, max_tokens=500, temperature=0.1)
    if not raw:
        return None
    raw = raw.replace("\n", " | ")
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    return parts or None


def _realign(parts, toks):
    """Rebuild segments from the child's EXACT tokens using only the model's
    boundary positions (per-segment token counts). Refuses if counts differ —
    we never let the LLM rewrite a word."""
    counts = [len(p.split()) for p in parts]
    if sum(counts) != len(toks) or 0 in counts:
        return None
    segs, i = [], 0
    for c in counts:
        segs.append(" ".join(toks[i : i + c]))
        i += c
    return segs


def _marker_split(text):
    parts = [p.strip() for p in re.split(r"[.!?;।,…]+", text) if p.strip()]
    return parts or [text]


def segment(text):
    """Split one answer into utterances of the child's exact words.

    Ladder: exact -> realign -> strict retry -> marker fallback.
    Returns (utterances, method_label)."""
    text = _norm(text)
    if not text:
        return [], "empty"
    toks = text.split()
    # Only trivially short answers skip the ladder. Anything longer goes to
    # the LLM — sparse speech ("சாதம்… தயிர்…") arrives as short fragments,
    # and treating a 5-word answer as one utterance inflates MLU for exactly
    # the children this screen needs to catch.
    if len(toks) <= 2:
        return [text], "single"

    for strict, label in ((False, ""), (True, "strict_")):
        parts = _llm_parts(text, strict)
        if not parts:
            continue
        if _norm(" ".join(parts)) == text:
            return parts, label + "exact"
        realigned = _realign(parts, toks)
        if realigned:
            return realigned, label + "realign"
    return _marker_split(text), "marker"


# --------------------------------------------------------------------- metrics


def words_of(utterance):
    out = []
    for tok in utterance.split():
        tok = tok.strip(_PUNCT)
        if tok:
            out.append(tok)
    return out


def metrics(utterances):
    per_utt = [words_of(u) for u in utterances]
    per_utt = [w for w in per_utt if w]
    all_words = [w for ws in per_utt for w in ws]
    total = len(all_words)
    unique = len({w.casefold() for w in all_words})
    n_utt = len(per_utt)
    return {
        "utterances": n_utt,
        "total_words": total,
        "unique_words": unique,
        "ttr": round(unique / total, 2) if total else 0.0,
        "longest": max((len(ws) for ws in per_utt), default=0),
        "mlu": round(total / n_utt, 2) if n_utt else 0.0,
        "code_mixed": sum(1 for w in all_words if re.search(r"[A-Za-z]", w)),
    }


# ---------------------------------------------------------------- norms verdict


def band_for(age_months):
    for (lo, hi), band in prompts.NORMS.items():
        if lo <= age_months <= hi:
            return band
    # clamp to nearest band so an out-of-range age still gets a comparison
    bands = sorted(prompts.NORMS.items())
    return bands[0][1] if age_months < bands[0][0][0] else bands[-1][1]


def verdict(m, age_months):
    if m["total_words"] < 40:
        return "sample_too_short"
    band = band_for(age_months)
    below = 0
    if m["mlu"] < band["mlu"][0]:
        below += 1
    if m["longest"] < band["longest"]:
        below += 1
    if m["total_words"] >= 150 and m["unique_words"] < band["unique"]:
        below += 1
    if below >= 2:
        return "worth_mentioning"
    if below == 1:
        return "keep_watching"
    return "tracking_well"


def metric_breakdown(m, age_months):
    """Rows of (metric, value, typical band, status) — status ✓ / ⚠ / n/a."""
    band = band_for(age_months)
    lo, hi = band["mlu"]
    rows = [
        {
            "metric": "MLU (words per utterance)",
            "value": f"{m['mlu']:.2f}",
            "typical": f"{lo}–{hi}",
            "status": "✓" if m["mlu"] >= lo else "⚠",
        },
        {
            "metric": "Longest utterance",
            "value": m["longest"],
            "typical": f"≥ {band['longest']} words",
            "status": "✓" if m["longest"] >= band["longest"] else "⚠",
        },
        {
            "metric": "Unique words",
            "value": m["unique_words"],
            "typical": f"≥ {band['unique']} (needs 150+ word sample)",
            "status": (
                "n/a"
                if m["total_words"] < 150
                else ("✓" if m["unique_words"] >= band["unique"] else "⚠")
            ),
        },
        {
            "metric": "Sample size (total words)",
            "value": m["total_words"],
            "typical": "≥ 40 to screen",
            "status": "✓" if m["total_words"] >= 40 else "⚠",
        },
    ]
    return rows


# ------------------------------------------------------------ guardrails (code)

PAED_SENTENCE = (
    "If you would like a fuller picture, a paediatrician or a speech-language "
    "pathologist can take a proper look."
)

_PAED_SENT_RE = re.compile(r"[^.!?]*p(?:a)?ediatrician[^.!?]*[.!?]?\s*", re.IGNORECASE)
_CONDITION_SENT_RE = re.compile(
    r"[^.!?]*\b(autis\w+|adhd|apraxia|dysarthria|dyslexia|stutter\w*|"
    r"disorder\w*|impairment\w*|speech delay|language delay|diagnos\w+)\b"
    r"[^.!?]*[.!?]?\s*",
    re.IGNORECASE,
)

_PRONOUN_SUBS = [
    (r"\b[Hh]e/[Ss]he\b", "they"),
    (r"\bhe\b", "they"),
    (r"\bHe\b", "They"),
    (r"\bshe\b", "they"),
    (r"\bShe\b", "They"),
    (r"\bhim\b", "them"),
    (r"\bHim\b", "Them"),
    (r"\bhis\b", "their"),
    (r"\bHis\b", "Their"),
    (r"\bher\b", "their"),
    (r"\bHer\b", "Their"),
    (r"\bhers\b", "theirs"),
    (r"\bhimself\b", "themselves"),
    (r"\bherself\b", "themselves"),
    (r"\bthey is\b", "they are"),
    (r"\bThey is\b", "They are"),
    (r"\bthey was\b", "they were"),
    (r"\bThey was\b", "They were"),
    (r"\bthey has\b", "they have"),
    (r"\bThey has\b", "They have"),
    (r"\bthey does\b", "they do"),
    (r"\bThey does\b", "They do"),
    (r"\bthey('|’)s\b", "they're"),
    (r"\bThey('|’)s\b", "They're"),
]


def guard(text, verdict_str, append_paed=False):
    """Code-level guardrails for any family-facing English text."""
    text = (text or "").strip()
    text = _PAED_SENT_RE.sub("", text)
    text = _CONDITION_SENT_RE.sub("", text)
    for pat, repl in _PRONOUN_SUBS:
        text = re.sub(pat, repl, text)
    text = re.sub(r"([.!?])(?=[^\s.!?])", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if append_paed and verdict_str == "worth_mentioning":
        text = (text + " " + PAED_SENTENCE).strip()
    return text


# ---------------------------------------------------- family-facing text (LLM)

_VERDICT_PLAIN = {
    "tracking_well": "the numbers sit inside the typical band for this age",
    "keep_watching": "one number sits a little below the typical band — worth "
    "keeping an eye on across a few more chats",
    "worth_mentioning": "more than one number sits below the typical band for "
    "this age",
    "sample_too_short": "the chat was too short to screen fairly — under 40 "
    "words in total",
}

# Register lock: none of these may appear in analysis/briefing text unless
# the verdict is tracking_well. One regeneration, then deterministic fallback.
_BANNED_TONE_RE = re.compile(
    r"typical for (?:their|this|his|her) age|\bexcellent\b|\bimpressive\b|"
    r"\ba joy\b|\bnormal\b|\bon track\b|\bwhich is typical\b",
    re.IGNORECASE,
)


def tone_ok(text, verdict_str):
    if verdict_str == "tracking_well":
        return True
    return not _BANNED_TONE_RE.search(text or "")


def age_str(age_months):
    years, rem = divmod(age_months, 12)
    if rem == 0:
        return f"{years} years ({age_months} months)"
    return f"{years} years {rem} months ({age_months} months)"


def _fact_payload(m, age_months, verdict_str, breakdown):
    band = band_for(age_months)
    return {
        "age": age_str(age_months),
        "metrics": m,
        "typical": {
            "mlu": list(band["mlu"]),
            "longest_min": band["longest"],
            "unique_min_if_150_words": band["unique"],
        },
        "metric_statuses": [
            {"metric": r["metric"], "status": r["status"]} for r in breakdown
        ],
        "verdict": verdict_str,
    }


def _fallback_analysis(m, age_months, verdict_str):
    band = band_for(age_months)
    lo, hi = band["mlu"]
    if verdict_str == "sample_too_short":
        return (
            f"This chat captured only {m['total_words']} words, which is too "
            "few to judge fairly — we need at least 40. At "
            f"{age_str(age_months)}, a longer, relaxed play session will give "
            "a much fairer picture."
        )
    parts = [
        f"In this chat we counted {m['total_words']} words across "
        f"{m['utterances']} little utterances.",
        f"On average each utterance was {m['mlu']:.2f} words long (typical "
        f"band: {lo}–{hi}), and the longest stretch was {m['longest']} words "
        f"(typical: {band['longest']} or more).",
    ]
    if m["total_words"] >= 150:
        parts.append(
            f"We heard {m['unique_words']} different words "
            f"(typical: {band['unique']} or more)."
        )
    parts.append(f"Overall, {_VERDICT_PLAIN[verdict_str]}.")
    parts.append(
        "One short play-chat is a snapshot, not the whole picture — children "
        "vary a lot day to day."
    )
    return " ".join(parts)


def analysis(m, age_months, verdict_str, breakdown):
    """'What the numbers say' — LLM, fact-locked and tone-locked in code,
    with deterministic fallback."""
    user = json.dumps(
        _fact_payload(m, age_months, verdict_str, breakdown), ensure_ascii=False
    )
    text = voice.chat(prompts.ANALYSIS_SYSTEM, user, max_tokens=300, temperature=0.4)
    if not text or len(text.split()) < 15 or not tone_ok(text, verdict_str):
        text = voice.chat(
            prompts.ANALYSIS_SYSTEM,
            user + "\nREMINDER: metrics marked ⚠ are BELOW the typical band — "
            "never call them typical; match the register to the verdict.",
            max_tokens=300,
            temperature=0.2,
        )
    if not text or len(text.split()) < 15 or not tone_ok(text, verdict_str):
        text = _fallback_analysis(m, age_months, verdict_str)
    return guard(text, verdict_str, append_paed=True)


_FALLBACK_PLAY = [
    ((24, 35), "Point-and-name walks work wonders at this age — around the "
     "house or street, take turns naming everything you both spot."),
    ((36, 59), "Try a 'what happened today' game at dinner — everyone tells "
     "one tiny story, and the child goes first."),
    ((60, 96), "Play 'why chains' — answer every question with another gentle "
     "question ('ஏன்?') and see how long the chain grows."),
]


_FALLBACK_BRIEFING = {
    "tracking_well": "The numbers sit comfortably inside the typical band — "
    "keep chatting, singing and playing just as you are.",
    "keep_watching": "One of the numbers sits a little below the typical "
    "band. We'd love to hear more of their words — this week's play plan is "
    "a lovely place to start, together.",
    "worth_mentioning": "A couple of the numbers sit below the typical band "
    "for this age. We'd love to hear more of their words — here's how to "
    "help this week, one little game at a time.",
    "sample_too_short": "Today's chat was on the short side, so the numbers "
    "can't tell us much yet. Another, longer play session will give a much "
    "fairer picture.",
}


def _fallback_card(answers, m, age_months, verdict_str):
    longest_line = ""
    for a in answers:
        for seg in a.get("segments", [a.get("text", "")]):
            if len(words_of(seg)) > len(words_of(longest_line)):
                longest_line = seg
    briefing = (
        f"You had a lovely little chat — {m['total_words']} words across "
        f"{m['utterances']} turns. " + _FALLBACK_BRIEFING[verdict_str]
    )
    lovely = (
        f'A favourite moment: "{longest_line}" — a full {len(words_of(longest_line))}'
        "-word stretch, all their own words."
        if longest_line
        else "Every answer today was the child's own words — that is the whole point."
    )
    play = _FALLBACK_PLAY[-1][1]
    for (lo, hi), idea in _FALLBACK_PLAY:
        if lo <= age_months <= hi:
            play = idea
    return {"briefing": briefing, "lovely_moment": lovely, "play_idea": play}


def _parse_json(raw):
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def card(answers, m, age_months, verdict_str, breakdown, child_name=""):
    """Family briefing / lovely moment / play idea — LLM JSON with
    deterministic fallback; briefing register is tone-locked in code and
    every field passes through guard()."""
    convo = [
        {"q": a.get("question", ""), "a": a.get("text", "")}
        for a in answers
        if a.get("text")
    ]
    payload = _fact_payload(m, age_months, verdict_str, breakdown)
    payload["child_name"] = child_name
    payload["conversation"] = convo
    user = json.dumps(payload, ensure_ascii=False)

    data = _parse_json(voice.chat(prompts.CARD_SYSTEM, user, max_tokens=400, temperature=0.6))
    if data and not tone_ok(str(data.get("briefing", "")), verdict_str):
        data = _parse_json(
            voice.chat(
                prompts.CARD_SYSTEM,
                user + "\nREMINDER: the verdict is not tracking_well — the "
                "briefing must be warm but honest, never celebratory.",
                max_tokens=400,
                temperature=0.3,
            )
        )
    fb = _fallback_card(answers, m, age_months, verdict_str)
    if not data:
        data = fb
    out = {}
    for key in ("briefing", "lovely_moment", "play_idea"):
        val = str(data.get(key) or fb[key])
        if key == "briefing" and not tone_ok(val, verdict_str):
            val = fb["briefing"]
        out[key] = guard(val, verdict_str, append_paed=(key == "briefing"))
    return out


# ------------------------------------------------------------ weekly play plan

_PLAN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
_PLAN_KEYS = ("day", "activity_name", "what_to_say_ta", "what_to_say_en", "builds")
_NOT_THERAPY_RE = re.compile(r"\b(therap\w+|training|exercises?)\b", re.IGNORECASE)

# Deterministic activity pools, targeted-first when a metric is below band.
_EXPANSION_POOL = [
    ("சொல்லு-சேர்ப்பு echo", "நீ சொன்னதை நானும் சொல்றேன் — ஒரு வார்த்தை சேர்த்து! 'பந்து'ன்னா 'சிவப்பு பந்து'!",
     "I'll say what you said — with one word added! 'Ball' becomes 'red ball'!",
     "Longer phrases"),
    ("என்ன ஆச்சு கதை", "இன்னிக்கு என்ன ஆச்சு? முதல்ல என்ன, அப்புறம் என்ன, கடைசில என்ன?",
     "What happened today? What came first, then what, and at the end?",
     "Longer phrases"),
    ("பாட்டு நிறுத்தம்", "பாட்டு பாடும்போது திடீர்னு நிறுத்துவேன் — அடுத்த வரி நீ சொல்லு!",
     "I'll suddenly pause our song — you say the next line!",
     "Longer phrases"),
]
_NAMING_POOL = [
    ("சமையலறை சஃபாரி", "சமையலறைல இது என்ன? இது எதுக்கு? எந்த கலர்?",
     "In the kitchen — what's this? What's it for? What colour?",
     "New words"),
    ("ஜன்னல் விளையாட்டு", "ஜன்னல்ல என்ன என்ன தெரியுது? ஒவ்வொண்ணா சொல்லு!",
     "What can you see out the window? Name them one by one!",
     "New words"),
    ("கடை விளையாட்டு", "நம்ம வீட்டுக் கடைல என்ன வாங்கணும்? list சொல்லு!",
     "What shall we buy at our pretend shop? Tell me the list!",
     "New words"),
]
_MIX_POOL = [
    ("மாத்தி மாத்தி பேசு", "முதல்ல நீ ஒண்ணு சொல்லு, அப்புறம் நான் ஒண்ணு சொல்றேன் — மாத்தி மாத்தி!",
     "First you say one, then I say one — taking turns!",
     "Turn-taking"),
    ("பொம்மை phone", "பொம்மை phone-ல பாட்டிகிட்ட பேசலாமா? என்ன சொல்லுவ?",
     "Shall we call grandma on the toy phone? What will you say?",
     "Turn-taking"),
    ("நான் யாரு?", "நான் ஒரு விலங்கு மாதிரி நடிக்கிறேன் — நான் யாருன்னு கேள்வி கேட்டு கண்டுபிடி!",
     "I'll act like an animal — ask me questions and guess who I am!",
     "Turn-taking"),
]


def plan_focus(breakdown):
    """Skills below band, from the ⚠ rows — what the plan should target."""
    focus = []
    for row in breakdown:
        if row["status"] != "⚠":
            continue
        name = row["metric"].lower()
        if "mlu" in name or "longest" in name:
            focus.append("longer phrases (below typical band)")
        elif "unique" in name:
            focus.append("new words (vocabulary below typical band)")
    return focus


def _fallback_plan(breakdown):
    focus = " ".join(plan_focus(breakdown))
    pools = []
    if "longer phrases" in focus:
        pools.append(_EXPANSION_POOL)
    if "new words" in focus:
        pools.append(_NAMING_POOL)
    pools.append(_MIX_POOL)
    pools.append(_EXPANSION_POOL)
    pools.append(_NAMING_POOL)
    seen, picked = set(), []
    for pool in pools:
        for item in pool:
            if item[0] not in seen:
                seen.add(item[0])
                picked.append(item)
            if len(picked) == 5:
                break
        if len(picked) == 5:
            break
    return [
        {
            "day": day,
            "activity_name": name,
            "what_to_say_ta": ta,
            "what_to_say_en": en,
            "builds": builds,
        }
        for day, (name, ta, en, builds) in zip(_PLAN_DAYS, picked)
    ]


def play_plan(m, age_months, verdict_str, breakdown):
    """5-day home play plan targeted at below-band metrics. One sarvam-30b
    call returning strict JSON; deterministic fallback if parsing fails.
    Never therapy, never training — enforced in code too."""
    payload = _fact_payload(m, age_months, verdict_str, breakdown)
    payload["focus_skills"] = plan_focus(breakdown) or ["enrichment — all bands met"]
    raw = voice.chat(
        prompts.PLAN_SYSTEM,
        json.dumps(payload, ensure_ascii=False),
        max_tokens=600,
        temperature=0.6,
    )
    plan = None
    if raw:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                cand = json.loads(match.group(0))
                if (
                    isinstance(cand, list)
                    and len(cand) == 5
                    and all(
                        isinstance(d, dict)
                        and all(str(d.get(k, "")).strip() for k in _PLAN_KEYS)
                        for d in cand
                    )
                ):
                    plan = cand
            except Exception:
                plan = None
    if plan is None:
        plan = _fallback_plan(breakdown)
    for i, d in enumerate(plan):
        d["day"] = _PLAN_DAYS[i]
        for k in ("activity_name", "what_to_say_en", "builds"):
            d[k] = _NOT_THERAPY_RE.sub("play", guard(str(d[k]), verdict_str))
        d["what_to_say_ta"] = str(d["what_to_say_ta"]).strip()
    return plan
