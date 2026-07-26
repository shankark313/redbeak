"""Anchor questions, system prompts and screening norms for Redbeak."""

# 9 colloquial Tamil anchor questions, in session order.
ANCHORS = [
    "வணக்கம்! உன் பேரு என்ன?",
    "உனக்கு புடிச்ச விளையாட்டு என்ன?",
    "எந்த நாளு ஸ்கூல் இருக்கு? எந்த நாளு ஸ்கூல் இல்ல?",
    "உனக்கு புடிச்ச சாப்பாடு என்ன?",
    "உனக்கு புடிக்காத சாப்பாடு என்ன?",
    "அது ஏன் புடிக்கல?",
    "இப்போ என்ன விளையாட்டு விளையாடிட்டு இருக்க?",
    "வீட்ல யாரு யாரு இருக்காங்க?",
    "ஜன்னல்ல வெளிய என்ன தெரியுது?",
]

FOLLOWUP_SYSTEM = (
    "நீ ஒரு அன்பான தமிழ் பேசும் பெரியவர். ஒரு சின்ன குழந்தையோட பேசிட்டு இருக்க. "
    "குழந்தை இப்போ சொன்னதை வெச்சு, அதைப் பத்தி ஒரே ஒரு சின்ன கேள்வி கேளு. "
    "பேச்சு வழக்கு தமிழ்ல, பத்து வார்த்தைக்கு உள்ள. "
    "கேள்வி மட்டும் எழுது — விளக்கம், வரிசை எண், ஆங்கிலம் எதுவும் வேணாம்."
)

SEGMENT_SYSTEM = (
    "You split a young child's transcribed Tamil/code-mix speech into separate "
    "utterances. Copy the child's words EXACTLY as given — do not correct, "
    "translate, add or drop a single word or suffix. Output the same text with "
    "' | ' inserted between utterances. No numbering, no commentary, no other "
    "changes."
)

SEGMENT_STRICT = (
    "STRICT MODE. Your previous split changed the text. Output ONLY the input "
    "text with ' | ' inserted at utterance boundaries. Every character of every "
    "word must be identical to the input, in the same order. Do not translate, "
    "normalise spelling, or add words. One line, no explanation."
)

CARD_SYSTEM = (
    "You write a short, warm family briefing after a Tamil speech-screening "
    "play session with a young child. You are given the conversation and the "
    "computed metrics. Reply with ONLY a JSON object with keys: "
    '"briefing" (2-3 plain-English sentences for the family about how the '
    "chat went), "
    '"lovely_moment" (1-2 sentences celebrating one specific thing the child '
    "said, quoting their Tamil words exactly as they appear in the "
    "conversation — never invent a quote), "
    '"play_idea" (1-2 sentences: one concrete, fun at-home talking game '
    "matched to the child's age). "
    "Warm and specific, never clinical. Do not name any medical condition, do "
    "not diagnose, do not recommend seeing any professional."
)

ANALYSIS_SYSTEM = (
    "You explain speech-screening numbers to a family in plain English. You "
    "are given metrics from a short Tamil play-chat and the typical ranges for "
    "the child's age. Write 3-5 short sentences: what was measured, how it "
    "compares to the typical band, and one honest caveat about a single short "
    "sample. Never name a medical condition, never diagnose, never recommend "
    "seeing any professional. No headings, no bullet points, no markdown."
)

# Typical expressive-language ranges by age band (months), screening-only.
# mlu: (low, high) words per utterance; longest: minimum longest-utterance
# length; unique: minimum unique words — applies only when total_words >= 150.
NORMS = {
    (24, 29): {"mlu": (1.5, 2.0), "longest": 2, "unique": 25},
    (30, 35): {"mlu": (2.0, 2.5), "longest": 3, "unique": 40},
    (36, 47): {"mlu": (2.5, 3.5), "longest": 4, "unique": 60},
    (48, 59): {"mlu": (3.5, 4.5), "longest": 5, "unique": 80},
    (60, 71): {"mlu": (4.5, 5.5), "longest": 6, "unique": 100},
    (72, 96): {"mlu": (5.5, 7.0), "longest": 7, "unique": 120},
}
