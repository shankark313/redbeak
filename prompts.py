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

# Static English glosses for the anchors, index-aligned with ANCHORS.
QUESTION_GLOSSES = [
    "Hi! What's your name?",
    "What's your favourite game?",
    "Which days do you have school? Which days is there no school?",
    "What's your favourite food?",
    "Which food don't you like?",
    "Why don't you like it?",
    "What game are you playing these days?",
    "Who all are at home?",
    "What can you see outside the window?",
]

# The ONLY generated text the parrot ever SPEAKS. Everything else that is
# TTS'd is hand-written in this file; sarvam-30b output for cards/plans/
# analysis is display-only and must never be routed to voice.tts.
FOLLOWUP_SYSTEM = (
    "நீ ஒரு அன்பான தமிழ் பேசும் பெரியவர். ஒரு சின்ன குழந்தையோட பேசிட்டு இருக்க. "
    "குழந்தை இப்போ சொன்னதை வெச்சு, அதைப் பத்தி ஒரே ஒரு சின்ன கேள்வி கேளு.\n"
    "விதிகள்: பத்து வார்த்தைக்கு உள்ள. ஆமா/இல்லன்னு மட்டும் பதில் வர கேள்வி "
    "வேணாம் — குழந்தை நிறைய பேச வைக்கிற கேள்வி. குழந்தை சொன்ன வார்த்தையையே "
    "வெச்சு கேளு. Write EXACTLY as spoken Chennai Tamil — பேரு not பெயர், "
    "புடிச்ச not பிடித்த, இருக்கா not இருக்கிறதா; never literary/written "
    "register. கேள்வி மட்டும் எழுது — விளக்கம், வரிசை எண் எதுவும் வேணாம்.\n"
    "Examples:\n"
    'குழந்தை: "எனக்கு cricket பிடிக்கும்" → cricket-ஆ! யாரு கூட விளையாடுவே?\n'
    'குழந்தை: "ஸ்கூல்ல painting பண்ணேன்" → painting-ஆ! என்ன வரைஞ்சே சொல்லு!\n'
    'குழந்தை: "பூனை பால் குடிச்சுச்சு" → அப்புறம் பூனை என்ன பண்ணுச்சு?\n'
    'குழந்தை: "அம்மா கூட கடைக்கு போனேன்" → கடைல என்ன என்ன வாங்கினீங்க?'
)

SEGMENT_SYSTEM = (
    "You split a young child's (age 2-6) transcribed Tamil/Hindi code-mix "
    "speech into separate utterances. Keep every grammatically connected phrase "
    "together as ONE utterance — never split a verb from its subject or "
    "object. Split only between disconnected bursts: an isolated noun, a "
    "repeated fragment, or a standalone word like 'இல்ல' or 'தெரியல' that "
    "does not connect to the phrase before it. Copy the child's words "
    "EXACTLY as given — do not correct, translate, add or drop a single word "
    "or suffix. Output the same text with ' | ' inserted between utterances. "
    "No numbering, no commentary, no other changes.\n"
    "Example 1 (connected speech — keep whole):\n"
    "Input: எனக்கு தோசை ரொம்ப புடிக்கும் அம்மா சுட்டு தருவாங்க\n"
    "Output: எனக்கு தோசை ரொம்ப புடிக்கும் | அம்மா சுட்டு தருவாங்க\n"
    "Example 2 (fragment bursts — split):\n"
    "Input: சாதம் தயிர் தயிர் சாதம் தெரியல\n"
    "Output: சாதம் | தயிர் | தயிர் சாதம் | தெரியல\n"
    "Example 3 (one connected sentence — no split at all):\n"
    "Input: ஜன்னல் வெளிய ஒரு பெரிய மரம் தெரியுது\n"
    "Output: ஜன்னல் வெளிய ஒரு பெரிய மரம் தெரியுது"
)

SEGMENT_STRICT = (
    "STRICT MODE. Your previous split changed the text. Output ONLY the input "
    "text with ' | ' inserted at utterance boundaries. Every character of every "
    "word must be identical to the input, in the same order. Do not translate, "
    "normalise spelling, or add words. One line, no explanation."
)

CARD_SYSTEM = (
    "You write a short, warm family briefing after a Tamil speech-screening "
    "play session with a young child. You are given the conversation, the "
    "child's age (a ready-made string — restate it only from that string), "
    "the computed metrics with per-metric statuses (✓ within band, ⚠ below "
    "band, n/a), and the overall verdict. Reply with ONLY a JSON object with "
    "keys: "
    '"briefing" (2-3 plain-English sentences for the family about how the '
    "chat went), "
    '"lovely_moment" (1-2 sentences celebrating one specific thing the child '
    "said, quoting their words exactly as they appear in the "
    "conversation — never invent a quote), "
    '"play_idea" (1-2 sentences: one concrete, fun at-home talking game '
    "matched to the child's age). "
    "REGISTER RULES for the briefing — match the verdict exactly: "
    "celebratory ONLY when the verdict is tracking_well. When it is "
    "keep_watching or worth_mentioning, be warm, honest and encouraging — "
    "acknowledge what the child did, say plainly that some numbers sit below "
    "the typical band, and that you'd love to hear more of their words, with "
    "the family's help this week; never use words like excellent, impressive "
    "or 'a joy' there. When it is sample_too_short, say warmly that too few "
    "words were captured to judge and encourage a longer play session. "
    "Warm and specific, never clinical. Do not name any medical condition, do "
    "not diagnose, do not recommend seeing any professional."
)

ANALYSIS_SYSTEM = (
    "You explain speech-screening numbers to a family in plain English. You "
    "are given the child's age as a ready-made string, metrics from a short "
    "Tamil play-chat, the typical ranges for that age, each metric's status "
    "(✓ within band, ⚠ below band, n/a), and the overall verdict. Write 3-5 "
    "short sentences: what was measured, how it compares, one honest caveat "
    "about a single short sample. HARD RULES: restate the age ONLY from the "
    "provided age string, never recompute it. NEVER describe a metric whose "
    "status is ⚠ as typical, fine or strong — say plainly it sits below the "
    "typical band. When two or more metrics are ⚠, the register is warm but "
    "concerned — do not celebrate. When the verdict is sample_too_short, say "
    "plainly that too few words were captured to judge fairly and a longer "
    "play session is needed. The session's duration was not measured — never "
    "mention minutes or how long it lasted; 'months' in the age refers to the "
    "child's age, not time. Never name a medical condition, never diagnose, "
    "never recommend seeing any professional. No headings, no bullet points, "
    "no markdown."
)

SUMMARY_SYSTEM = (
    "You interpret a Tamil speech-screening result for a parent, as one "
    "overall picture. You are given the child's age as a ready-made string, "
    "the metrics, each metric's status (✓ within band, ⚠ below band, n/a), "
    "and the verdict. Write 3-4 short plain-English sentences: what was "
    "measured (a short play conversation), what the numbers mean TOGETHER — "
    "the overall picture of sentence length and vocabulary versus typical "
    "ranges for this age, never metric-by-metric — and what the verdict "
    "means in plain words. HARD RULES: restate the age ONLY from the "
    "provided age string. Never describe anything whose status is ⚠ as "
    "typical, fine or strong. Match the register to the verdict: warm and "
    "happy only for tracking_well; warm but honest otherwise; for "
    "sample_too_short say plainly the chat was too short to judge. Do NOT "
    "give advice or a next step — that is added separately. Never name a "
    "medical condition, never diagnose, never recommend any professional. "
    "No headings, no bullets, no markdown."
)

PLAN_SYSTEM = (
    "You design a playful 5-day (Monday–Friday) home play plan for a "
    "Tamil-speaking family, to grow a young child's talking through everyday "
    "games. You are given the child's age string, the screening metrics with "
    "statuses, and focus skills (anything below the typical band — target "
    "those first; if none, make it joyful enrichment). Reply with ONLY a JSON "
    "array of exactly 5 objects with keys: "
    '"day" (Monday..Friday), '
    '"activity_name" (short playful name), '
    '"what_to_say_ta" (one line of colloquial spoken Tamil the parent '
    "actually says during the game), "
    '"what_to_say_en" (its English translation), '
    '"builds" (one short line: the skill it builds — longer phrases, new '
    "words, or turn-taking). "
    "Rules: every activity must fit the age. If MLU is below band, prefer "
    "expansion games — the parent repeats the child's phrase and adds one "
    "word. If vocabulary is below band, prefer naming games. Never call "
    "anything therapy, training or an exercise. Never name a medical "
    "condition. No text outside the JSON array."
)

# Practice scenario packs: themed conversational mini-sessions. Each prompt
# escalates openness — scene-setting first, wide-open retell/lists last.
SCENARIOS = [
    {
        "id": "cat_story",
        "title_ta": "பூனை கதை",
        "title_en": "Cat story",
        "emoji": "🐱",
        "prompts": [
            {"ta": "கேளு! ஒரு சின்ன பூனை இருந்துச்சு. அதுக்கு ஒரு சிவப்பு "
                   "பந்து ரொம்ப புடிக்கும். ஒரு நாள் அந்த பந்து உருண்டு போய் "
                   "சோஃபா அடியில ஒளிஞ்சுக்கிச்சு. பூனை தேடி தேடி கடைசில "
                   "கண்டுபிடிச்சுது! கதை முடிஞ்சுது. உனக்கு கதை புடிச்சுதா?",
             "en": "Listen! There was a little cat. It loved its red ball. "
                   "One day the ball rolled away and hid under the sofa. The "
                   "cat searched and searched and finally found it! The end. "
                   "Did you like the story?"},
            {"ta": "இப்போ நீ சொல்லு! பூனை கதைய உன் வார்த்தைல நீயே சொல்லு!",
             "en": "Now you tell it! Tell the cat story in your own words!"},
            {"ta": "பூனையோட பந்து எங்க போய் ஒளிஞ்சுக்கிச்சு?",
             "en": "Where did the cat's ball go and hide?"},
            {"ta": "பூனை பந்த கண்டுபிடிச்சப்போ எப்படி இருந்திருக்கும்? சொல்லு!",
             "en": "How do you think the cat felt when it found the ball? "
                   "Tell me!"},
        ],
    },
    {
        "id": "market_trip",
        "title_ta": "கடைக்கு போலாம்",
        "title_en": "Market trip",
        "emoji": "🛒",
        "prompts": [
            {"ta": "கடைக்கு போலாம் வா! நாம என்ன என்ன வாங்கலாம்? சொல்லு!",
             "en": "Let's go to the shop! What shall we buy? Tell me!"},
            {"ta": "நீ சொன்னதுல உனக்கு ரொம்ப புடிச்சது எது? அது என்ன கலர்?",
             "en": "Which of those do you like most? What colour is it?"},
            {"ta": "கடைக்கு யார் யார் கூட போலாம்? எப்படி போலாம்?",
             "en": "Who shall we take along to the shop? How shall we go?"},
            {"ta": "கடைல வேற என்ன என்ன பாக்கலாம்? பெரிய list சொல்லு!",
             "en": "What else can we see at the shop? Give me a big list!"},
        ],
    },
    {
        "id": "zoo_day",
        "title_ta": "விலங்கு தோட்டம்",
        "title_en": "Zoo day",
        "emoji": "🦁",
        "prompts": [
            {"ta": "இன்னிக்கு விலங்கு தோட்டம் போறோம்! முதல்ல எந்த விலங்கு "
                   "பாக்கணும்?",
             "en": "We're going to the zoo today! Which animal shall we see "
                   "first?"},
            {"ta": "அந்த விலங்கு என்ன சாப்பிடும்? எப்படி இருக்கும்?",
             "en": "What does that animal eat? What does it look like?"},
            {"ta": "யானை எப்படி சத்தம் போடும்? சிங்கம்? நீ சத்தம் பண்ணி "
                   "சொல்லு!",
             "en": "What sound does an elephant make? A lion? Make the "
                   "sounds and tell me!"},
            {"ta": "தோட்டத்துல இன்னும் என்ன என்ன பாக்கலாம்? சொல்லு!",
             "en": "What else can we see at the zoo? Tell me!"},
        ],
    },
    {
        "id": "cooking",
        "title_ta": "சமையல்",
        "title_en": "Cooking together",
        "emoji": "🍳",
        "prompts": [
            {"ta": "இன்னிக்கு நாம ரெண்டு பேரும் சேர்ந்து சமைக்கலாம்! என்ன "
                   "சமைக்கலாம்?",
             "en": "Today let's cook together, you and me! What shall we "
                   "make?"},
            {"ta": "அதுக்கு என்ன என்ன வேணும்? சொல்லு பாப்போம்!",
             "en": "What do we need for it? Let's list them!"},
            {"ta": "முதல்ல என்ன பண்ணணும்? அப்புறம் என்ன பண்ணணும்?",
             "en": "What do we do first? And then what?"},
            {"ta": "சமைச்சது யாருக்கு யாருக்கு கொடுக்கலாம்? ஏன்?",
             "en": "Who shall we give our food to? Why?"},
        ],
    },
    {
        "id": "rainy_day",
        "title_ta": "மழை நாள்",
        "title_en": "Rainy day",
        "emoji": "🌧️",
        "prompts": [
            {"ta": "வெளிய மழை பெய்யுது! ஜன்னல்ல பாரு — என்ன என்ன தெரியுது?",
             "en": "It's raining outside! Look out the window — what can "
                   "you see?"},
            {"ta": "மழைல நனைஞ்சா என்ன ஆகும்? உனக்கு நனைய புடிக்குமா?",
             "en": "What happens if we get wet in the rain? Do you like "
                   "getting wet?"},
            {"ta": "மழை நாள்ல வீட்டுக்குள்ள என்ன விளையாடலாம்?",
             "en": "What can we play indoors on a rainy day?"},
            {"ta": "மழை நின்னதும் வெளிய போய் என்ன பண்ணலாம்?",
             "en": "When the rain stops, what shall we do outside?"},
        ],
    },
]

# ---------------------------------------------------------------- Hindi pack
# Natural SPOKEN Hindi, tum register, conversational not shuddh.

ANCHORS_HI = [
    "नमस्ते! तुम्हारा नाम क्या है?",
    "तुम्हें कौन सा game खेलना पसंद है?",
    "school किस किस दिन होता है? किस दिन नहीं होता?",
    "तुम्हें कौन सा खाना सबसे अच्छा लगता है?",
    "कौन सा खाना अच्छा नहीं लगता?",
    "वो क्यों अच्छा नहीं लगता?",
    "आजकल कौन सा खेल खेल रहे हो?",
    "घर में कौन कौन रहता है?",
    "खिड़की से बाहर क्या क्या दिखता है?",
]

QUESTION_GLOSSES_HI = list(QUESTION_GLOSSES)  # same English meanings

FOLLOWUP_SYSTEM_HI = (
    "तुम एक प्यारे बड़े हो, एक छोटे बच्चे से हिंदी में बात कर रहे हो। "
    "बच्चे ने अभी जो कहा, उसी के बारे में बस एक छोटा सवाल पूछो।\n"
    "नियम: दस शब्दों के अंदर। ऐसा सवाल नहीं जिसका जवाब सिर्फ़ हाँ/नहीं हो — "
    "बच्चे को खूब बोलने दो। बच्चे के ही शब्द इस्तेमाल करो। Write EXACTLY as "
    "spoken bolchaal Hindi — 'tumhara naam kya hai' register, कभी shuddh/"
    "literary नहीं। हमेशा tum कहो — कभी 'आप' मत कहो, बच्चा है। "
    "सिर्फ़ सवाल लिखो — कोई explanation या numbering नहीं।\n"
    "Examples:\n"
    'बच्चा: "mujhe cricket pasand hai" → cricket! किसके साथ खेलते हो?\n'
    'बच्चा: "school mein painting ki" → painting! क्या बनाया, बताओ!\n'
    'बच्चा: "billi ne doodh piya" → फिर billi ने क्या किया?\n'
    'बच्चा: "mummy ke saath bazar gaya" → बाज़ार में क्या क्या खरीदा?'
)

SCENARIOS_HI = [
    {
        "id": "cat_story",
        "title_ta": "बिल्ली की कहानी",
        "title_en": "Cat story",
        "emoji": "🐱",
        "prompts": [
            {"ta": "सुनो! एक छोटी बिल्ली थी। उसे अपनी लाल गेंद बहुत पसंद "
                   "थी। एक दिन गेंद लुढ़क कर sofa के नीचे छुप गई। बिल्ली ने "
                   "खूब ढूंढा और आखिर में ढूंढ ही ली! बस, कहानी खत्म। "
                   "तुम्हें कहानी अच्छी लगी?",
             "en": "Listen! There was a little cat. It loved its red ball. "
                   "One day the ball rolled away and hid under the sofa. The "
                   "cat searched and searched and finally found it! The end. "
                   "Did you like the story?"},
            {"ta": "अब तुम सुनाओ! बिल्ली वाली कहानी अपने शब्दों में सुनाओ!",
             "en": "Now you tell it! Tell the cat story in your own words!"},
            {"ta": "बिल्ली की गेंद कहाँ जाकर छुपी थी?",
             "en": "Where did the cat's ball go and hide?"},
            {"ta": "गेंद मिलने पर बिल्ली को कैसा लगा होगा? बताओ!",
             "en": "How do you think the cat felt when it found the ball? "
                   "Tell me!"},
        ],
    },
    {
        "id": "market_trip",
        "title_ta": "चलो दुकान",
        "title_en": "Market trip",
        "emoji": "🛒",
        "prompts": [
            {"ta": "चलो दुकान चलते हैं! हम क्या क्या खरीदें? बताओ!",
             "en": "Let's go to the shop! What shall we buy? Tell me!"},
            {"ta": "इनमें से तुम्हें सबसे ज़्यादा क्या पसंद है? वो किस रंग "
                   "का है?",
             "en": "Which of those do you like most? What colour is it?"},
            {"ta": "दुकान पर किस किस को साथ ले चलें? कैसे चलें?",
             "en": "Who shall we take along to the shop? How shall we go?"},
            {"ta": "दुकान में और क्या क्या देख सकते हैं? लंबी list बताओ!",
             "en": "What else can we see at the shop? Give me a big list!"},
        ],
    },
    {
        "id": "zoo_day",
        "title_ta": "चिड़ियाघर",
        "title_en": "Zoo day",
        "emoji": "🦁",
        "prompts": [
            {"ta": "आज हम चिड़ियाघर जा रहे हैं! सबसे पहले कौन सा जानवर "
                   "देखें?",
             "en": "We're going to the zoo today! Which animal shall we see "
                   "first?"},
            {"ta": "वो जानवर क्या खाता है? कैसा दिखता है?",
             "en": "What does that animal eat? What does it look like?"},
            {"ta": "हाथी कैसे आवाज़ करता है? शेर? आवाज़ निकाल कर बताओ!",
             "en": "What sound does an elephant make? A lion? Make the "
                   "sounds and tell me!"},
            {"ta": "चिड़ियाघर में और क्या क्या देख सकते हैं? बताओ!",
             "en": "What else can we see at the zoo? Tell me!"},
        ],
    },
    {
        "id": "cooking",
        "title_ta": "साथ में खाना बनाएँ",
        "title_en": "Cooking together",
        "emoji": "🍳",
        "prompts": [
            {"ta": "आज हम दोनों साथ में खाना बनाते हैं! क्या बनाएँ?",
             "en": "Today let's cook together, you and me! What shall we "
                   "make?"},
            {"ta": "उसके लिए क्या क्या चाहिए? बताओ!",
             "en": "What do we need for it? Let's list them!"},
            {"ta": "सबसे पहले क्या करना होगा? फिर क्या?",
             "en": "What do we do first? And then what?"},
            {"ta": "बना हुआ खाना किस किस को दें? क्यों?",
             "en": "Who shall we give our food to? Why?"},
        ],
    },
    {
        "id": "rainy_day",
        "title_ta": "बारिश का दिन",
        "title_en": "Rainy day",
        "emoji": "🌧️",
        "prompts": [
            {"ta": "बाहर बारिश हो रही है! खिड़की से देखो — क्या क्या दिखता "
                   "है?",
             "en": "It's raining outside! Look out the window — what can "
                   "you see?"},
            {"ta": "बारिश में भीग जाएँ तो क्या होता है? तुम्हें भीगना पसंद "
                   "है?",
             "en": "What happens if we get wet in the rain? Do you like "
                   "getting wet?"},
            {"ta": "बारिश वाले दिन घर के अंदर क्या खेल सकते हैं?",
             "en": "What can we play indoors on a rainy day?"},
            {"ta": "बारिश रुकने पर बाहर जाकर क्या करें?",
             "en": "When the rain stops, what shall we do outside?"},
        ],
    },
]

# ------------------------------------------------------------- language packs
# Everything per-language the engine needs. "ta" fields in scenarios/feeds
# carry the spoken line regardless of language; glosses stay English.
LANGS = {
    "ta-IN": {
        "label": "தமிழ்",
        "anchors": ANCHORS,
        "glosses": QUESTION_GLOSSES,
        "scenarios": SCENARIOS,
        "followup_system": FOLLOWUP_SYSTEM,
        "followup_user": 'குழந்தை வயசு: {age} மாசம்.\nகுழந்தை இப்போ சொன்னது: "{text}"',
        "fallback_lines": ["அப்புறம் என்ன ஆச்சு? சொல்லு!", "இன்னும் கொஞ்சம் சொல்லு!"],
    },
    "hi-IN": {
        "label": "हिन्दी",
        "anchors": ANCHORS_HI,
        "glosses": QUESTION_GLOSSES_HI,
        "scenarios": SCENARIOS_HI,
        "followup_system": FOLLOWUP_SYSTEM_HI,
        "followup_user": 'बच्चे की उम्र: {age} महीने।\nबच्चे ने अभी कहा: "{text}"',
        "fallback_lines": ["फिर क्या हुआ? बताओ!", "और बताओ!"],
    },
}

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
