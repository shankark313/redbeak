#!/usr/bin/env python
"""Redbeak live — hands-free conversation mode.

    python live.py --name Sthira --age 60 [--scenario cat_story | --anchors]

Speaks each prompt aloud (cached TTS via afplay), listens on the mic with
silence-detected turn taking, transcribes with codemix STT, asks one
adaptive follow-up per prompt, and on finish (or Ctrl+C) runs the full
analyst pipeline and saves the session in the app's sessions/ format —
so it shows up in Past sessions and Progress with per-turn audio.
"""

import argparse
import io
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np
import sounddevice as sd

import prompts
import voice
from pipeline import build_results, slug

SR = 16000
BLOCK = 1024

MODE_LABEL = "Live (hands-free)"


def status(msg, end=False):
    sys.stdout.write(f"\r   [{msg}]" + " " * 20 + ("\n" if end else ""))
    sys.stdout.flush()


def speak(text, speaker):
    audio = voice.tts(text, speaker=speaker)
    if not audio:
        print("   (TTS unavailable — reading silently)")
        return
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio)
        path = f.name
    subprocess.run(["afplay", path], check=False)


def calibrate():
    """0.5s of ambient noise -> silence threshold (mean RMS * 3, floored)."""
    print("🎚  calibrating ambient noise (0.5s)…")
    rec = sd.rec(int(0.5 * SR), samplerate=SR, channels=1, dtype="int16")
    sd.wait()
    ambient = float(np.sqrt(np.mean(rec.astype(np.float64) ** 2)))
    threshold = max(ambient * 3, 120.0)
    print(f"   ambient RMS {ambient:.0f} → speech threshold {threshold:.0f}")
    return threshold


def record_turn(threshold, max_s=25.0, silence_s=1.8):
    """Capture one child turn: wait for speech to start, then for it to stop
    (RMS below threshold for silence_s). Returns int16 mono array or None if
    no speech was heard before the cap."""
    frames = []
    heard_speech = False
    silent_since = None
    t0 = time.time()
    status("listening…")
    with sd.InputStream(
        samplerate=SR, channels=1, dtype="int16", blocksize=BLOCK
    ) as stream:
        while True:
            data, _ = stream.read(BLOCK)
            frames.append(data.copy())
            rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
            now = time.time()
            if rms > threshold:
                if not heard_speech:
                    heard_speech = True
                    status("heard speech…")
                silent_since = None
            elif heard_speech:
                if silent_since is None:
                    silent_since = now
                elif now - silent_since >= silence_s:
                    status("done ✓", end=True)
                    break
            if now - t0 >= max_s:
                status("time cap reached", end=True)
                break
    if not heard_speech:
        return None
    return np.concatenate(frames).reshape(-1)


def to_wav(audio):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(audio.tobytes())
    return buf.getvalue()


def capture_answer(threshold, question, q_gloss, is_followup, session_id,
                   seq, mode, max_s, silence_s):
    """One listen -> transcribe -> print. Returns the answer dict or None."""
    from pipeline import transcribe_answer

    audio = record_turn(threshold, max_s=max_s, silence_s=silence_s)
    if audio is None:
        print("   (no speech heard — moving on)")
        return None
    ans = transcribe_answer(
        to_wav(audio), "wav", question, mode, is_followup,
        session_id, seq, question_gloss=q_gloss,
    )
    if ans["text"]:
        print(f"   🧒 {ans['text']}")
        if ans.get("gloss"):
            print(f"      ({ans['gloss']})")
    else:
        print("   (couldn't make out any words)")
    return ans


def main():
    ap = argparse.ArgumentParser(description="Redbeak hands-free live session")
    ap.add_argument("--name", required=True, help="child's name")
    ap.add_argument("--age", type=int, required=True, help="age in months")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--scenario", help="practice scenario id (e.g. cat_story)")
    grp.add_argument("--anchors", action="store_true",
                     help="use the 9 screening anchors (default)")
    ap.add_argument("--voice", default="shubh", help="bulbul:v3 speaker")
    ap.add_argument("--prompts", type=int, default=0,
                    help="limit number of prompts (0 = all)")
    ap.add_argument("--max-turn", type=float, default=25.0,
                    help="max seconds per child turn")
    ap.add_argument("--silence", type=float, default=1.8,
                    help="seconds of silence that end a turn")
    args = ap.parse_args()

    if args.scenario:
        sc = next((s for s in prompts.SCENARIOS if s["id"] == args.scenario), None)
        if not sc:
            ids = ", ".join(s["id"] for s in prompts.SCENARIOS)
            sys.exit(f"unknown scenario '{args.scenario}' — pick from: {ids}")
        q_list = list(sc["prompts"])
        print(f"🦜 Redbeak live — {sc['emoji']} {sc['title_en']} with {args.name}")
    else:
        q_list = [
            {"ta": q, "en": g}
            for q, g in zip(prompts.ANCHORS, prompts.QUESTION_GLOSSES)
        ]
        print(f"🦜 Redbeak live — screening chat with {args.name}")
    if args.prompts:
        q_list = q_list[: args.prompts]

    threshold = calibrate()
    session_id = f"live_{time.strftime('%Y%m%d_%H%M%S')}_{slug(args.name)}"
    answers = []

    try:
        for i, p in enumerate(q_list, 1):
            print(f"\n🦜 [{i}/{len(q_list)}] {p['ta']}")
            print(f"   ({p['en']})")
            speak(p["ta"], args.voice)
            ans = capture_answer(
                threshold, p["ta"], p["en"], False, session_id,
                len(answers) + 1, MODE_LABEL, args.max_turn, args.silence,
            )
            if not ans:
                continue
            answers.append(ans)
            if not ans["text"].strip():
                continue
            fu = voice.followup(ans["text"], args.age)
            if not fu:
                continue
            fu_gloss = voice.gloss(fu) or "(asking a little more about what they said)"
            print(f"\n🦜 💬 {fu}")
            print(f"   ({fu_gloss})")
            speak(fu, args.voice)
            ans2 = capture_answer(
                threshold, fu, fu_gloss, True, session_id,
                len(answers) + 1, MODE_LABEL, args.max_turn, args.silence,
            )
            if ans2:
                answers.append(ans2)
    except KeyboardInterrupt:
        print("\n\n👋 ending early — analysing what we have…")

    if not answers:
        print("\nno answers captured — nothing to analyse.")
        return

    print("\n⏳ running the analyst…")
    session = build_results(args.name, args.age, MODE_LABEL, answers, session_id)
    m = session["metrics"]
    print("\n" + "=" * 56)
    print(f"  {args.name} · {session['age_months']} months · {session['verdict']}")
    print(f"  MLU {m['mlu']:.2f} · longest {m['longest']} · "
          f"{m['total_words']} words ({m['unique_words']} unique) · "
          f"{m['utterances']} utterances")
    for r in session["breakdown"]:
        print(f"   {r['status']:>3}  {r['metric']:<28} {r['value']:>6}  "
              f"typical {r['typical']}")
    print("=" * 56)
    print(f"\nsaved — open the app to see it under Past sessions "
          f"({session['id']}).")
    print("Screening prompt, not a diagnosis. A speech-language pathologist "
          "assesses language fully.")


if __name__ == "__main__":
    main()
