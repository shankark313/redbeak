# Redbeak 🦜

> A talkback app that catches speech delays in kids early — through a
> 4-minute talking game with a parrot, in colloquial Tamil or Hindi.

**The problem.** 1 in 12 Indian children has a speech delay. Most parents
learn of it from a school at age 8 — years after the signs were visible and
after the window where therapy works best. Screening needs a speech-language
pathologist: India has only a few thousand, urban and costly.

## What it does

A parrot talks to your child, hands-free, in the Tamil or Hindi they actually
speak at home. The child answers out loud; nobody has to type or tap.

Every answer is transcribed verbatim in code-mix mode — Tamil or Hindi with
English words left in Latin script, the way kids really talk — and the child's
exact words are then measured: how long their sentences are, the longest one
they managed, how many different words they used, how big the sample was.
Those numbers are compared against published age norms by deterministic code.

The verdict is honest and narrow: *tracking well*, *keep watching*, *worth
mentioning to your paediatrician*, or *the chat was too short to screen
fairly*. That strongest verdict is the ceiling — Redbeak never names a
condition and never diagnoses.

From there: a week of play ideas with lines for the parent to say, practice
scenarios (a cat story, a market trip, a rainy day) that are play and carry
no verdict at all, and a progress view that tracks how the sentences grow
across sessions.

## How it works

**Streamlit UI**, four pages:

| Page | What it is |
| --- | --- |
| 🎤 Session | Screening chat, mic or file upload. Guided (9 anchor questions) or Conversational (one adaptive follow-up per anchor). 4 / 6 / 9 turns. |
| 🔴 Live | Launches `live.py` and streams its event feed — parrot line, child's words, English gloss, per-turn audio. |
| 🧸 Practice | Scenario play chats. Same metrics, no verdict, no screening language. |
| 📈 Progress | Longitudinal journey per child. Fully deterministic, zero LLM calls. |

**`live.py`** is the hands-free voice engine. It calibrates on half a second
of ambient noise to set a speech threshold, then takes turns by silence: 1.8s
below threshold ends the child's turn, 25s caps it. Sessions end themselves —
a turn budget (default 6 parrot questions), an exit after two silent turns —
and always on a warm closing line, never a cut-off. Finishing is two-phase: a
marker-split summary lands within a second of Stop with zero network calls,
then the full pipeline refines it. Once finishing starts, SIGINT is ignored,
so a session always lands in a finished state.

**`pipeline.py`** is the shared analysis path, with no Streamlit imports —
that's what lets the CLI write sessions in exactly the app's format, so a
`live.py` run shows up under Past sessions and Progress like any other.

**Segmentation never rewrites the child.** `analyst.py` runs a ladder: accept
the model's split only if it reproduces the text exactly; otherwise rebuild
the segments from the child's own tokens using only the model's boundary
positions; otherwise retry strict; otherwise fall back to punctuation. If the
token counts don't match, the split is refused. The metrics are then plain
arithmetic over those words.

**All AI runs through Sarvam.** Saaras v3 for STT (`mode="codemix"`, language
pinned so short child utterances don't drift). Sarvam-30B for follow-ups,
segmentation and family-facing text — with `reasoning_effort=None`, which is
load-bearing: without it the model returns English chain-of-thought as
content. Bulbul v3 for TTS at pace 0.75, synthesized per sentence and stitched
with 400ms pauses client-side, disk-cached by content hash. sarvam-translate
for the English glosses. **Supabase** holds children, sessions and practice
logs — optional, and a no-op when the keys are unset.

Two design details worth calling out:

**The two-tier speech rule.** Anything the parrot *says* is either a
hand-written line from `prompts.py` or model output that survived
`voice.clean()` — script check for the session language, single plausible
line, 15 words max, `<think>` blocks stripped, and `None` when nothing safe
survives, in which case the parrot falls back to script. Anything generated
for the *parent* — briefing cards, play-plan lines — is display-only and is
never routed to TTS. The tiers are marked at both call sites.

**Guardrails in code, not prompts.** The paediatrician sentence is appended
if and only if the verdict is `worth_mentioning`, and regex-stripped
otherwise. Condition names — autism, ADHD, apraxia, "speech delay",
"diagnos\*" — are stripped from any family-facing sentence. Unknown pronouns
become they/them. A register lock bans "excellent", "normal", "on track" and
friends unless the verdict is `tracking_well`, with one regeneration and then
a deterministic fallback. None of this depends on the model complying.

## Honest limits

Expressive language only — not articulation, comprehension, pragmatics or
fluency.

The age norms are English-derived; Tamil is agglutinative, so word-based MLU
underestimates. Hindi carries the same caveat.

A 4-minute chat is a screen, never a diagnosis. Verdicts are stable across
runs; point estimates jitter about ±0.5.

More in [NOTES.md](NOTES.md).

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SARVAM_API_KEY=...          # required
export SUPABASE_URL=...            # optional — records + cross-device history
export SUPABASE_KEY=...            # optional

streamlit run app.py
```

Hands-free, from the terminal:

```bash
python live.py --name Sthira --age 60                     # screening chat
python live.py --name Sthira --age 60 --scenario cat_story --practice
python live.py --name Sthira --age 60 --lang hi-IN
```

Sessions auto-save to `sessions/` as JSON plus per-turn audio. The sidebar
re-renders any past session with zero API calls, or batch-runs a folder of
`a01..a09` audio files straight to results.

| File | Role |
| --- | --- |
| `app.py` | Streamlit UI — four pages, session flow, results, persistence |
| `live.py` | Hands-free voice engine: silence-detected turns, self-ending sessions |
| `pipeline.py` | Shared analysis path used by both the app and the CLI |
| `analyst.py` | Segmentation ladder, metrics, norms verdict, family text, guardrails |
| `voice.py` | Sarvam STT / TTS / chat / translate wrappers |
| `prompts.py` | Anchor questions, scenarios, system prompts, age-band norms |
| `store.py` | Supabase read/write — no-op when unset |

## Status

Built in one day at the Sarvam Epoch Buildathon (26 Jul 2026), Bengaluru.
