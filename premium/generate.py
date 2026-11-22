"""LLM-powered topic generator for the premium pipeline (NVIDIA NIM).

This is the "scripts without expiration" system: instead of looping back
through the 4-5 curated topics in premium/scripts.py and re-uploading
duplicate content, the queue pulls from a GROWING library
(premium/topics_library.json) that this module appends to.

  generate_topic(angle, category)   -> validated topic dict (premium TOPICS shape)
  ensure_unpublished(library, published_ids, min_count)
                                     -> generates fresh topics until the library
                                        has >= min_count unpublished entries;
                                        appends them. Returns count generated.

Uses NVIDIA Build (integrate.api.nvidia.com) via the OpenAI SDK — free-tier
access to meta/llama-3.3-70b-instruct, which is strong enough for the
channel's brutal-direct stoic voice. If NVIDIA_API_KEY is missing or the call
fails, callers (queue / publish.yml) fall back to the curated TOPICS so the
pipeline never blocks on LLM availability.

No LLM runs at publish time unless the library is low on unpublished topics —
the generated scripts are curated IP once written, exactly like scripts.py.
"""
import json
import os
import re
import time

from openai import OpenAI

import config
from premium import scripts as S

# ----- NVIDIA NIM client -----------------------------------------------------
BASE_URL = config.NVIDIA_BASE_URL          # https://integrate.api.nvidia.com/v1
MODEL = config.NVIDIA_MODEL                # meta/llama-3.3-70b-instruct
LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "topics_library.json")

# valid Mixkit clip_categories (must match premium/mixkit.CATEGORIES)
CLIP_CATEGORIES = ["nature", "mountains", "city", "sea", "sky", "road", "abstract", "business"]
TOPIC_CATEGORIES = ["Stoicism", "Discipline", "Mindset", "Success"]


def _client() -> OpenAI:
    key = config.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY") or ""
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set (needed for topic generation)")
    return OpenAI(base_url=BASE_URL, api_key=key)


# ----- angle pool (variety insurance) ----------------------------------------
# Each entry: (id, category, angle prompt). The generator is given ONE angle.
# Once the pool is exhausted, generate_novel() asks the LLM for a fresh angle
# not already in the library, so the supply never expires.
ANGLES = [
    ("memento-mori", "Stoicism", "Memento mori — death is not morbid, it is the lens that makes today matter. Stop living as if you have unlimited Tuesdays."),
    ("resistance-is-the-medicine", "Discipline", "The resistance you avoid is the medicine you need. The thing you keep putting off is the thing that would fix you."),
    ("stop-outsourcing-self-worth", "Mindset", "Stop outsourcing your self-worth to strangers online. The number under a post is not your value."),
    ("loneliness-price-of-becoming", "Mindset", "Loneliness is the price of becoming someone. The old crowd falls away when you start climbing."),
    ("anger-downstream-emotion", "Stoicism", "Anger is a downstream emotion. It always points at something underneath you have not looked at."),
    ("priority-not-time", "Success", "You do not have a time problem. You have a priority problem. Everyone has the same 24 hours; you are spending yours wrong."),
    ("consistency-beats-intensity", "Discipline", "Consistency beats intensity. The person who shows up average every day beats the person who shows up perfect once a month."),
    ("boredom-where-growth-happens", "Mindset", "Boredom is where growth actually happens. Your phone exists to keep you from the quiet where your life would catch up with you."),
    ("you-are-what-you-repeatedly-do", "Stoicism", "You are what you repeatedly do. Not what you intend, not what you plan when life calms down — what you actually do today."),
    ("illusion-of-motivation", "Discipline", "The illusion of motivation. Waiting to feel like it is the most expensive mistake you will ever make."),
    ("the-five-people", "Mindset", "You become the average of the five people you spend the most time with. Audit yours honestly."),
    ("stop-performing-your-life", "Mindset", "Stop performing your life for an audience that is not watching. The version of you that exists when nobody is looking is the only real one."),
    ("pain-as-information", "Stoicism", "Pain is information, not punishment. It is your body or mind telling you something is wrong — listen instead of numbing it."),
    ("the-mirror-test", "Discipline", "The mirror test. The one person you cannot lie to is the one looking back. Be honest with them tonight."),
    ("constraint-breeds-creativity", "Success", "Constraint breeds creativity. Unlimited options paralyze; a tight box forces you to actually build something."),
    ("envy-reveals-what-you-want", "Mindset", "Envy reveals what you actually want. Stop feeling guilty about it and use it as a compass."),
    ("the-trap-of-potential", "Discipline", "The trap of potential. Being called 'smart' as a child is why you are scared to try anything you might fail at now."),
    ("finish-what-you-start", "Discipline", "Finish what you start. The graveyard of half-started projects is the reason your life feels unfinished."),
    ("silence-as-power", "Stoicism", "Silence as power. The person who speaks least in the room usually controls it. Stop filling every gap with noise."),
    ("fear-of-being-average", "Mindset", "The fear of being average is making you miserable. Most lives are ordinary. An ordinary life lived well is enough."),
    ("control-what-you-can", "Stoicism", "The dichotomy of control. Some things are up to you, most are not. Worrying about the second category is what is breaking you."),
    ("slow-growth-real-growth", "Success", "Slow growth is real growth. The overnight successes you envy were ten years of unseen work."),
    ("the-cost-of-honesty", "Stoicism", "The cost of honesty. Telling the truth will cost you people. Lying will cost you yourself. Choose which loss you can live with."),
    ("stop-negotiating-with-tomorrow", "Discipline", "Stop negotiating with tomorrow. 'I'll start Monday' is the lie that has cost you years. Monday is not coming; today is here."),
    ("the-weight-of-unspoken-things", "Mindset", "The weight of unspoken things. What you refuse to say out loud is what is making you tired."),
    ("comparison-with-your-past-self", "Mindset", "The only fair comparison is with who you were a year ago. Not the strangers online — the version of you that you are quietly outrunning."),
    ("discipline-is-self-respect", "Discipline", "Discipline is self-respect in motion. Every promise you keep to yourself is a deposit into the account of who you are becoming."),
    ("the-empty-room-test", "Stoicism", "The empty room test. Who would you be if no one ever saw you again, no one praised you, no one judged you? That person is who you actually need to become."),
]


# ----- prompts ---------------------------------------------------------------
SYSTEM_PROMPT = """You are the lead scriptwriter for @StickVerse, a cinematic stoic / discipline motivation channel on YouTube.

Your voice: David Goggins crossed with Marcus Aurelius crossed with a man who has been knocked down and got back up. Second person ("you"), present tense, brutal-direct, no fluff, no clichés. Every line should make a comfortable person uncomfortable.

BANNED WORDS (never use — they are the fingerprints of a soft writer):
  journey, unlock, level up, best self, embrace the process, trust the journey,
  manifest, abundance, vibration, energy, gratitude practice, self-care, toxic,
  gaslighting, boundaries (therapy sense), healing era, main character energy,
  soft girl era, protected at all costs, worthiness, you got this.

STRUCTURE (6 scenes, ~550 words total, ~85-95 words per scene):
  1. HOOK     — a jarring opening line that is impossible to scroll past. No greeting.
  2. PROBLEM  — name the cost of the current behavior in concrete terms.
  3. SHIFT    — the reframe (often a Stoic principle) that turns the problem upside down.
  4. CORE     — the mechanism: WHY the shift works, not just that it does.
  5. APPLICATION — what to do today, concretely. Small, specific, doable now.
  6. RESOLUTION — close the loop on the hook. End on a single hard statement, not a question.

RULES:
  - No emoji, no markdown, no asterisks, no [pause] markers, no questions to the audience.
  - Sentences vary 3-25 words. Mix short punches with longer reflective runs.
  - Each scene's narration is ONE continuous paragraph (no line breaks within).
  - Plain prose only — no scene labels, no numbering in the narration itself.

You output ONLY a valid JSON object, no markdown fences, no commentary."""


USER_PROMPT = """Write ONE video script for the angle below.

ANGLE (the contrarian thesis — lean INTO it, do not soften it): {angle}
CATEGORY: {category}

Output strict JSON in this EXACT shape (field names + structure must match exactly):

{{
  "id": "kebab-case-id-4-to-6-words",
  "category": "{category}",
  "title": "a YouTube title under 70 chars, clickbait-grade, no emoji, no question, Title Case the important words",
  "hook_line": "the EXACT first sentence of scene 1 (the pattern-interrupt open)",
  "recurring_phrase": "a 2-5 word anchor phrase that appears 2-3 times across the scenes",
  "thumbnail_text": "2-4 BOLD UPPERCASE words for the thumbnail overlay, different from the title, max 4 words",
  "scenes": [
    {{"narration": "scene 1 (~85-95 words, the HOOK)", "clip_category": "one of: nature, mountains, city, sea, sky, road, abstract, business"}},
    {{"narration": "scene 2 (~85-95 words, the PROBLEM)", "clip_category": "..."}},
    {{"narration": "scene 3 (~85-95 words, the SHIFT)", "clip_category": "..."}},
    {{"narration": "scene 4 (~85-95 words, the CORE)", "clip_category": "..."}},
    {{"narration": "scene 5 (~85-95 words, the APPLICATION)", "clip_category": "..."}},
    {{"narration": "scene 6 (~85-95 words, the RESOLUTION)", "clip_category": "..."}}
  ],
  "description": "a 120-180 word YouTube description in the same brutal tone. First line restates the hook. End with one line of 5 hashtags (no # symbols in this field, just comma-separated words).",
  "tags": ["10 lowercase tags as a JSON array, including the category, the angle, and broad motivation terms"],
  "hashtags": ["4 lowercase hashtags as a JSON array (without # symbol)"]
}}

The hook_line MUST be the verbatim first sentence of scenes[0].narration.
The recurring_phrase MUST appear verbatim inside at least two scenes' narration.
The 6 clip_category values should vary across scenes (don't repeat the same one 6 times).
Total narration across all 6 scenes: 500-600 words.

Return ONLY the JSON object."""


# ----- validation ------------------------------------------------------------
def validate_topic(topic: dict) -> None:
    """Raise ValueError with a clear message if the topic is malformed."""
    required = ["id", "category", "title", "hook_line", "recurring_phrase",
                "thumbnail_text", "scenes", "description", "tags", "hashtags"]
    missing = [f for f in required if f not in topic or topic[f] in ("", None, [])]
    if missing:
        raise ValueError(f"missing/empty fields: {missing}")

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", topic["id"]):
        raise ValueError(f"bad id '{topic['id']}' (lowercase kebab-case, 3-60 chars)")

    scenes = topic["scenes"]
    if not isinstance(scenes, list) or len(scenes) != 6:
        raise ValueError(f"expected exactly 6 scenes, got {len(scenes) if isinstance(scenes, list) else 'non-list'}")

    total_words = 0
    for i, s in enumerate(scenes):
        if "narration" not in s or not s["narration"]:
            raise ValueError(f"scene {i} missing narration")
        if "clip_category" not in s or s["clip_category"] not in CLIP_CATEGORIES:
            raise ValueError(f"scene {i} bad clip_category '{s.get('clip_category')}' (must be one of {CLIP_CATEGORIES})")
        nw = len(s["narration"].split())
        if nw < 60 or nw > 130:
            raise ValueError(f"scene {i} narration is {nw} words (need 60-130)")
        total_words += nw
    if total_words < 450 or total_words > 700:
        raise ValueError(f"total narration {total_words} words (need 450-700)")

    # hook_line must be the verbatim start of scene 1
    if not topic["scenes"][0]["narration"].strip().startswith(topic["hook_line"].strip()[:40]):
        raise ValueError("hook_line is not the start of scene 1 narration")

    if not isinstance(topic["tags"], list) or len(topic["tags"]) < 5:
        raise ValueError("tags must be a list of >= 5")
    if not isinstance(topic["hashtags"], list) or len(topic["hashtags"]) < 3:
        raise ValueError("hashtags must be a list of >= 3")

    # strip markdown contamination from narration (LLMs sometimes add ** or #)
    for s in scenes:
        s["narration"] = re.sub(r"\*\*|\*_|#\s*", "", s["narration"]).strip()


# ----- generation ------------------------------------------------------------
def _call_llm(angle: str, category: str, retries: int = 3) -> dict:
    client = _client()
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT.format(angle=angle, category=category)},
                ],
                temperature=0.85,
                top_p=0.9,
                max_tokens=8000,   # Nemotron Ultra is a reasoning model — needs headroom
                                   # for ~600-1500 reasoning tokens before the JSON content
                response_format={"type": "json_object"},
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                # reasoning models sometimes spend every token on reasoning_content;
                # surface that so the retry logic can kick in
                raise RuntimeError("empty content (reasoning consumed the budget)")
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError as e:
            last_err = ValueError(f"JSON parse failed: {e}")
            print(f"  [generate] attempt {attempt+1} JSON parse failed: {e}")
            time.sleep(4 * (attempt + 1))
        except Exception as e:
            last_err = e
            print(f"  [generate] attempt {attempt+1} failed: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"LLM generation failed after {retries} attempts: {last_err}")


def generate_topic(angle_id: str, category: str, angle_prompt: str) -> dict:
    """Generate + validate one topic. Returns a dict in the premium TOPICS shape."""
    print(f"[generate] angle={angle_id} category={category}")
    topic = _call_llm(angle_prompt, category)
    # ensure id matches the angle (deterministic-ish; overrides LLM's id)
    topic["id"] = angle_id
    topic["category"] = category
    validate_topic(topic)
    words = sum(len(s["narration"].split()) for s in topic["scenes"])
    print(f"[generate] OK: {topic['id']} — {topic['title'][:60]}  ({words} words)")
    return topic


# ----- library ---------------------------------------------------------------
def load_library(path: str = LIBRARY_PATH) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_library(topics: list, path: str = LIBRARY_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def append_topic(topic: dict, path: str = LIBRARY_PATH) -> None:
    lib = load_library(path)
    # dedupe by id
    if any(t.get("id") == topic["id"] for t in lib):
        print(f"[generate] topic {topic['id']} already in library; skipping append")
        return
    lib.append(topic)
    save_library(lib, path)
    print(f"[generate] appended to library ({len(lib)} topics total): {path}")


def unpublished_library_topics(published_ids: set, path: str = LIBRARY_PATH) -> list:
    """Library topics whose id is NOT in published_ids (i.e. not yet uploaded)."""
    lib = load_library(path)
    return [t for t in lib if t.get("id") not in published_ids]


def _used_angle_ids(path: str = LIBRARY_PATH) -> set:
    return {t.get("id") for t in load_library(path)}


def ensure_unpublished(published_ids: set, min_count: int = 2,
                       path: str = LIBRARY_PATH, api_key: str = None) -> int:
    """Generate fresh topics until the library has >= min_count unpublished
    entries. Appends each to the library. Returns the number generated.

    Iterates the ANGLES pool (skipping ids already in the library); if the pool
    is exhausted, falls back to generate_novel() which asks the LLM for a fresh
    angle. If NVIDIA_API_KEY is missing or generation fails, returns 0 and the
    caller falls back to curated TOPICS.
    """
    if api_key:
        os.environ["NVIDIA_API_KEY"] = api_key  # for _client() to pick up
    try:
        _client()  # raises if no key
    except RuntimeError as e:
        print(f"[generate] {e} — skipping generation, falling back to curated TOPICS")
        return 0

    generated = 0
    used = _used_angle_ids(path)
    pending = unpublished_library_topics(published_ids, path)
    print(f"[generate] library has {len(pending)} unpublished topic(s); target >= {min_count}")

    for angle_id, category, angle_prompt in ANGLES:
        if len(pending) >= min_count:
            break
        if angle_id in used or angle_id in published_ids:
            continue
        try:
            topic = generate_topic(angle_id, category, angle_prompt)
            append_topic(topic, path)
            used.add(angle_id)
            pending.append(topic)
            generated += 1
        except Exception as e:
            print(f"[generate] angle {angle_id} failed: {str(e)[:150]} — skipping")
            used.add(angle_id)  # don't retry a broken angle forever
            continue

    # pool exhausted but still under min_count -> ask LLM for a novel angle
    while len(pending) < min_count:
        try:
            topic = generate_novel(list(used | published_ids))
            append_topic(topic, path)
            used.add(topic["id"])
            pending.append(topic)
            generated += 1
        except Exception as e:
            print(f"[generate] novel-angle generation failed: {str(e)[:150]} — stopping")
            break

    print(f"[generate] generated {generated} new topic(s); library now has "
          f"{len(unpublished_library_topics(published_ids, path))} unpublished")
    return generated


NOVEL_PROMPT = """You are picking a FRESH angle for a stoic/discipline motivation video, distinct from every angle already covered in the channel's library.

Already-covered angle ids (do NOT repeat these themes): {used}

Propose ONE new angle that is not on that list and not a thin rephrase of any of them. It should be a contrarian, uncomfortable truth in the channel's voice (David Goggins × Marcus Aurelius). Then write the full 6-scene script for it.

Output the SAME JSON shape as before (id, category, title, hook_line, recurring_phrase, thumbnail_text, scenes[6], description, tags, hashtags). The id must be a new lowercase kebab-case string not in the list above. category must be one of: Stoicism, Discipline, Mindset, Success. Same scene/word/clip_category rules apply."""


def generate_novel(used_ids: list) -> dict:
    """Ask the LLM to propose + write a fresh angle not already covered."""
    print("[generate] asking LLM for a novel angle (pool exhausted)")
    client = _client()
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": NOVEL_PROMPT.format(used=", ".join(used_ids[:60]))},
                ],
                temperature=0.95,
                top_p=0.95,
                max_tokens=8000,
                response_format={"type": "json_object"},
            )
            raw = (resp.choices[0].message.content or "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            topic = json.loads(raw)
            if topic.get("id") in used_ids:
                topic["id"] = topic["id"] + "-" + str(int(time.time()))[-4:]
            validate_topic(topic)
            words = sum(len(s["narration"].split()) for s in topic["scenes"])
            print(f"[generate] OK novel: {topic['id']} — {topic['title'][:60]}  ({words} words)")
            return topic
        except Exception as e:
            print(f"[generate] novel attempt {attempt+1} failed: {type(e).__name__}: {str(e)[:150]}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("novel-angle generation failed after retries")


if __name__ == "__main__":
    # smoke test: generate one topic from the first angle + validate + print
    aid, cat, prompt = ANGLES[0]
    t = generate_topic(aid, cat, prompt)
    print(json.dumps(t, indent=2, ensure_ascii=False)[:1200])
