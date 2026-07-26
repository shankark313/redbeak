"""Sarvam voice + LLM helpers: TTS (disk-cached), STT (codemix), follow-ups.

Every network call is wrapped broadly — a failed call degrades (None / ""),
it never kills a session with a child mid-conversation.
"""

import base64
import hashlib
import io
import os
import re
import wave

from sarvamai import SarvamAI

import prompts

CACHE_DIR = "audio_cache"
PACE = 0.75
PAUSE_MS = 400
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+")
TAMIL_RE = re.compile("[\\u0B80-\\u0BFF]")
THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL)
SCRIPT_RE = {
    "ta-IN": TAMIL_RE,
    "hi-IN": re.compile("[ऀ-ॿ]"),  # Devanagari
}

_client = None


def client():
    global _client
    if _client is None:
        _client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY", ""))
    return _client


def _tts_raw(text, speaker, lang="ta-IN"):
    """One bulbul call -> wav bytes. Raises on failure (caller catches)."""
    resp = client().text_to_speech.convert(
        text=text,
        target_language_code=lang,
        model="bulbul:v3",
        speaker=speaker,
        pace=PACE,
    )
    return base64.b64decode(resp.audios[0])


def _concat_wavs(chunks, silence_ms=PAUSE_MS):
    """Stitch wav chunks with silence between them (bulbul has no SSML/break
    param, so sentence pauses are assembled client-side)."""
    if len(chunks) == 1:
        return chunks[0]
    with wave.open(io.BytesIO(chunks[0]), "rb") as w0:
        params = w0.getparams()
    silence = b"\x00" * (
        int(params.framerate * silence_ms / 1000)
        * params.sampwidth
        * params.nchannels
    )
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        for i, chunk in enumerate(chunks):
            with wave.open(io.BytesIO(chunk), "rb") as r:
                w.writeframes(r.readframes(r.getnframes()))
            if i < len(chunks) - 1:
                w.writeframes(silence)
    return out.getvalue()


def tts(text, speaker="shubh", lang="ta-IN"):
    """TTS -> wav bytes, disk-cached by (speaker, pace, pause, lang, text)
    hash (ta-IN keeps the legacy key so the warm cache stays valid).
    Multi-sentence lines are synthesized per sentence and stitched with a
    breathing pause. None on failure."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key_src = f"{speaker}|{PACE}|{PAUSE_MS}|{text}"
    if lang != "ta-IN":
        key_src += f"|{lang}"
    key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".wav")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    try:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        audio = _concat_wavs([_tts_raw(s, speaker, lang) for s in sentences])
        with open(path, "wb") as f:
            f.write(audio)
        return audio
    except Exception:
        return None


def warm_pack(lang="ta-IN"):
    """Pre-generate TTS for a language pack's hand-written spoken lines:
    the 9 anchors plus every scenario prompt (default voice)."""
    pack = prompts.LANGS[lang]
    for q in pack["anchors"]:
        tts(q, lang=lang)
    for sc in pack["scenarios"]:
        for p in sc["prompts"]:
            tts(p["ta"], lang=lang)


def warm_anchors():
    warm_pack("ta-IN")


def stt(audio_bytes, ext="wav", lang="ta-IN"):
    """Child audio -> transcript. codemix keeps English words in Latin
    script with native suffixes attached; language pinned so short child
    utterances don't drift to a sibling language. Empty string on failure."""
    if not audio_bytes:
        return ""
    try:
        buf = io.BytesIO(audio_bytes)
        buf.name = "answer." + ext
        resp = client().speech_to_text.transcribe(
            file=buf,
            model="saaras:v3",
            mode="codemix",
            language_code=lang,
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


def clean(raw, lang="ta-IN"):
    """Sanitize an LLM reply meant to be spoken to a child.

    Strips <think> blocks and numbered-reasoning lines, takes the last
    plausible line, requires the session language's script (Tamil or
    Devanagari), rejects >15 words. Returns None when nothing safe
    survives — caller falls back to script."""
    if not raw:
        return None
    script_re = SCRIPT_RE.get(lang, TAMIL_RE)
    text = strip_think(raw)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not re.match(r"^(\d+[.)]|[-*•])\s", ln)]
    for line in reversed(lines):
        if script_re.search(line):
            line = line.strip("\"'“”‘’ ")
            if len(line.split()) > 15:
                return None
            return line
    return None


def followup(child_text, age_months, lang="ta-IN"):
    """One short colloquial spoken-register follow-up about what the child
    said, in the session language. None means: skip silently."""
    if not child_text or not child_text.strip():
        return None
    pack = prompts.LANGS.get(lang, prompts.LANGS["ta-IN"])
    user = pack["followup_user"].format(age=age_months, text=child_text.strip())
    raw = chat(pack["followup_system"], user, max_tokens=80, temperature=0.8)
    out = clean(raw, lang=lang)
    # register lock: Hindi follow-ups must stay in tum register
    if out and lang == "hi-IN" and re.search(r"आप", out):
        return None
    return out


def gloss(text, lang="ta-IN"):
    """Muted English gloss of a native/code-mix line. 2 retries, then
    degrade to no gloss (httpx ReadTimeout is not an ApiError)."""
    if not text or not text.strip():
        return None
    for _ in range(2):
        try:
            resp = client().text.translate(
                input=text,
                source_language_code=lang,
                target_language_code="en-IN",
                model="sarvam-translate:v1",
            )
            out = (getattr(resp, "translated_text", None) or "").strip()
            if out:
                return out
        except Exception:
            continue
    return None
