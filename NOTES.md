# Redbeak — build notes

## Borderline starting point (flagged proactively)

I wrote prototype scripts the night before the event while learning the
Sarvam SDK — a REST question loop and a metrics script. The submitted agent
was rebuilt today from an empty repo on the Sarvam API: this repo's commit
history (10:4x onward) documents the day's build — conversational engine,
live hands-free mode, practice scenarios, two-tier speech rule, Supabase
records. Happy to walk a mentor through the diff.

## The metric

Screening coverage: from ~zero pre-age-5 speech screening to a 4-minute,
~₹5-per-session screen any Tamil-speaking family can run. (1-in-12
prevalence of speech-language delay per published epidemiology; SLP access
in India is scarce/urban/costly.)

## Honest limits

Expressive language only (not articulation, comprehension, pragmatics,
fluency); norms are English-derived — Tamil is agglutinative so word-MLU
underestimates; a 4-minute session is a screen, never a diagnosis; strongest
output is "worth mentioning to your paediatrician." Segmentation is
LLM-assisted: verdicts are stable across runs, point-estimates jitter ±0.5.

## Stack

100% Sarvam for AI: Saaras v3 STT (codemix, ta-IN pinned), Sarvam-30B
(reasoning_effort=None) for follow-ups/segmentation/family text, Bulbul v3
TTS (sentence-split + stitched pauses, pace 0.75), sarvam-translate glosses.
Streamlit UI, Supabase records, deterministic metrics vs published age bands.

Hindi added at the venue on Sarvam's suggestion — conversational Hindi
anchors; norms carry the same English-derived caveat as Tamil.
