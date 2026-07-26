# 🦜 Redbeak

A Tamil speech-milestone **screening** voice agent for children aged 2–6,
demoed via Streamlit. All AI (chat, STT, TTS, translation) runs through the
[Sarvam](https://sarvam.ai) Python SDK.

> Screening prompt, not a diagnosis. A speech-language pathologist assesses
> language fully.

## What it does

1. Speaks 9 colloquial Tamil anchor questions to the child (TTS, cache-warmed).
2. Records the child's answers (mic or file upload), transcribes them in
   code-mix mode (Tamil + English-in-Latin-script, the way Chennai kids talk).
3. In **Conversational** mode, asks one adaptive follow-up per anchor,
   referencing what the child actually said.
4. Segments answers into utterances (the child's exact words — never
   LLM-rewritten), computes screening metrics (MLU, longest utterance, unique
   words, TTR, code-mixing), and compares them against age-band norms.
5. Produces a verdict pill, a plain-English "what the numbers say" analysis,
   and a family briefing card — with guardrails enforced in code, not prompts.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SARVAM_API_KEY=...          # required
export SUPABASE_URL=...            # optional — session memory
export SUPABASE_KEY=...            # optional

streamlit run app.py
```

Sessions auto-save to `sessions/` (JSON + answer audio). The sidebar can
re-render any past session with zero API calls, or batch-run a folder of
`a01..a09` audio files straight to results.

## Files

| File | Role |
| --- | --- |
| `app.py` | Streamlit UI: session flow, results, persistence |
| `voice.py` | TTS (disk-cached), STT (codemix), follow-up generation |
| `analyst.py` | Segmentation ladder, metrics, norms verdict, briefing cards |
| `prompts.py` | Anchor questions, system prompts, age-band norms |
| `store.py` | Supabase write-back + previous-session memory (no-op if unset) |
