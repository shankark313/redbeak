"""Sarvam voice + LLM helpers: TTS (disk-cached), STT (codemix), follow-ups.

Every network call is wrapped broadly — a failed call degrades (None / ""),
it never kills a session with a child mid-conversation.
"""

import base64
import hashlib
import io
import os
import re

from sarvamai import SarvamAI

import prompts

CACHE_DIR = "audio_cache"
TAMIL_RE = re.compile("[\\u0B80-\\u0BFF]")
THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL)

_client = None


def client():
    global _client
    if _client is None:
        _client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY", ""))
    return _client


def tts(text):
    """Tamil TTS -> wav bytes, disk-cached by text hash. None on failure."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".wav")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    try:
        resp = client().text_to_speech.convert(
            text=text,
            target_language_code="ta-IN",
            model="bulbul:v3",
            speaker="shubh",
            pace=0.9,
        )
        audio = base64.b64decode(resp.audios[0])
        with open(path, "wb") as f:
            f.write(audio)
        return audio
    except Exception:
        return None


def warm_anchors():
    """Pre-generate TTS for all 9 anchor questions into the disk cache."""
    for q in prompts.ANCHORS:
        tts(q)


def stt(audio_bytes, ext="wav"):
    """Child audio -> transcript. codemix keeps English words in Latin script
    with Tamil suffixes attached; language pinned to ta-IN so short utterances
    don't drift to Telugu. Empty string on failure."""
    if not audio_bytes:
        return ""
    try:
        buf = io.BytesIO(audio_bytes)
        buf.name = "answer." + ext
        resp = client().speech_to_text.transcribe(
            file=buf,
            model="saaras:v3",
            mode="codemix",
            language_code="ta-IN",
        )
        return (getattr(resp, "transcript", None) or "").strip()
    except Exception:
        return ""


def strip_think(text):
    return THINK_RE.sub(" ", text or "")


def chat(system, user, max_tokens=300, temperature=0.4):
    """Raw sarvam-30b chat, <think> blocks stripped. None on any failure.
    reasoning_effort=None is load-bearing: without it the model returns
    English chain-of-thought as content."""
    try:
        resp = client().chat.completions(
            model="sarvam-30b",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            reasoning_effort=None,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return strip_think(resp.choices[0].message.content).strip()
    except Exception:
        return None


def clean(raw):
    """Sanitize an LLM reply meant to be spoken to a child.

    Strips <think> blocks and numbered-reasoning lines, takes the last
    plausible line, requires Tamil characters, rejects >15 words.
    Returns None when nothing safe survives — caller falls back to script."""
    if not raw:
        return None
    text = strip_think(raw)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not re.match(r"^(\d+[.)]|[-*•])\s", ln)]
    for line in reversed(lines):
        if TAMIL_RE.search(line):
            line = line.strip("\"'“”‘’ ")
            if len(line.split()) > 15:
                return None
            return line
    return None


def followup(child_text, age_months):
    """One short colloquial Tamil follow-up about what the child said.
    None means: skip silently, move to the next anchor."""
    if not child_text or not child_text.strip():
        return None
    user = (
        f"குழந்தை வயசு: {age_months} மாசம்.\n"
        f'குழந்தை இப்போ சொன்னது: "{child_text.strip()}"'
    )
    raw = chat(prompts.FOLLOWUP_SYSTEM, user, max_tokens=80, temperature=0.8)
    return clean(raw)


def gloss(text):
    """Muted English gloss of a Tamil/code-mix line. 2 retries, then degrade
    to no gloss (httpx ReadTimeout is not an ApiError — catch broadly)."""
    if not text or not text.strip():
        return None
    for _ in range(2):
        try:
            resp = client().text.translate(
                input=text,
                source_language_code="ta-IN",
                target_language_code="en-IN",
                model="sarvam-translate:v1",
            )
            out = (getattr(resp, "translated_text", None) or "").strip()
            if out:
                return out
        except Exception:
            continue
    return None
