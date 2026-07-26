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
    parts = [p.strip() for p in re.split(r"[.!?;।]+", text) if p.strip()]
    return parts or [text]


def segment(text):
    """Split one answer into utterances of the child's exact words.

    Ladder: exact -> realign -> strict retry -> marker fallback.
    Returns (utterances, method_label)."""
    text = _norm(text)
    if not text:
        return [], "empty"
    toks = text.split()
    if len(toks) <= 6:
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
            "value": m["mlu"],
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


def _fallback_analysis(m, age_months, verdict_str):
    band = band_for(age_months)
    lo, hi = band["mlu"]
    parts = [
        f"In this chat we counted {m['total_words']} words across "
        f"{m['utterances']} little utterances.",
        f"On average each utterance was {m['mlu']} words long (typical for this "
        f"age: {lo}–{hi}), and the longest stretch was {m['longest']} words "
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


def analysis(m, age_months, verdict_str):
    """'What the numbers say' — LLM with deterministic fallback, guarded."""
    band = band_for(age_months)
    user = json.dumps(
        {
            "age_months": age_months,
            "metrics": m,
            "typical": {
                "mlu": list(band["mlu"]),
                "longest_min": band["longest"],
                "unique_min_if_150_words": band["unique"],
            },
            "verdict": verdict_str,
        },
        ensure_ascii=False,
    )
    text = voice.chat(prompts.ANALYSIS_SYSTEM, user, max_tokens=300, temperature=0.4)
    if not text or len(text.split()) < 15:
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


def _fallback_card(answers, m, age_months, verdict_str):
    longest_line = ""
    for a in answers:
        for seg in a.get("segments", [a.get("text", "")]):
            if len(words_of(seg)) > len(words_of(longest_line)):
                longest_line = seg
    briefing = (
        f"You had a lovely little chat — {m['total_words']} words across "
        f"{m['utterances']} turns. " + _VERDICT_PLAIN[verdict_str].capitalize() + "."
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


def card(answers, m, age_months, verdict_str, child_name=""):
    """Family briefing / lovely moment / play idea — LLM JSON with
    deterministic fallback; every field passes through guard()."""
    convo = [
        {"q": a.get("question", ""), "a": a.get("text", "")}
        for a in answers
        if a.get("text")
    ]
    user = json.dumps(
        {
            "child_name": child_name,
            "age_months": age_months,
            "conversation": convo,
            "metrics": m,
        },
        ensure_ascii=False,
    )
    data = _parse_json(voice.chat(prompts.CARD_SYSTEM, user, max_tokens=400, temperature=0.6))
    fb = _fallback_card(answers, m, age_months, verdict_str)
    if not data:
        data = fb
    out = {}
    for key in ("briefing", "lovely_moment", "play_idea"):
        val = str(data.get(key) or fb[key])
        out[key] = guard(val, verdict_str, append_paed=(key == "briefing"))
    return out
