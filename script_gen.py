"""Generate the video script + scene breakdown via NVIDIA Build LLM.

Two-step:
1. Write a 2,800-3,400 word motivation script for the day's theme.
2. Break it into N scenes, each with narration + an image prompt for Flux.
"""
import json
import re
from openai import OpenAI
import config


def _client() -> OpenAI:
    if not config.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not set. Get one at https://build.nvidia.com")
    return OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY)


SYSTEM_PROMPT = """You are a ghostwriter for a YouTube motivation channel in the style of David Goggins crossed with Marcus Aurelius.

Your writing is sparse, brutal, and direct. No fluff. No clichés. Short punchy sentences mixed with longer reflective ones.

You write for men aged 18-35 who are tired of soft living. You NEVER use words like "journey", "unlock", "level up", "best self", "embrace the process", or "trust the journey". Those are banned.

You write like a man who has been knocked down and got back up. Not like a life coach."""

SCRIPT_PROMPT = """Write a 15-20 minute motivation script for a YouTube video.

Core message: {theme}
Category: {category}

Rules:
- Around 2,800-3,400 words (about 18 minutes when read at a slow deliberate pace).
- Open with a hook in the first 3 sentences. No "welcome back" or intro chatter.
- Use short paragraphs. Sentences vary between 5 and 25 words.
- Include 2-3 metaphorical turns the listener will remember a week later.
- No questions to the audience. No "you know what I mean?". Statements only.
- End with a single hard statement, not a question.
- No timestamps, no scene directions, no [pause] markers. Pure narration.
- No emoji, no asterisks, no markdown.

Write the script now. Plain text only."""

SCENE_PROMPT = """You are breaking a motivation script into visual scenes for a stick-figure slideshow video.

Each scene shows ONE minimalist stick-figure illustration for ~30 seconds while the narration plays.

Given the script below, break it into {n} sequential scenes. For each scene, output:
- narration: the exact words spoken during that scene (verbatim from the script, in order — every word of the script must appear across all scenes with nothing added or removed)
- image_prompt: a single-sentence description of a minimalist stick figure illustration showing the action or metaphor in that narration

Image prompt rules:
- ALWAYS start with exactly: "Minimalist stick figure illustration, single thin black line on cream off-white background, no shading, no color, sparse composition, lots of negative space, contemplative mood, flat 2D, "
- Then describe ONE concrete action or metaphor (e.g. "stick figure climbing a steep hill alone at dawn", "stick figure sitting on floor staring at empty wall", "stick figure pushing a boulder up a slope", "stick figure standing still while others run past").
- No text in the image. No detailed background scenery. Stick to the prefix style.

Also generate:
- title: a YouTube title (under 70 chars, no emoji, contains a strong verb, sounds like a statement not a question)
- description: a 200-word YouTube description in the same brutal tone as the script, ending with a single line of 5 hashtags
- tags: 10 lowercase comma-separated tags as a JSON array

Return ONLY a valid JSON object, no markdown fences, in this exact shape:
{{
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "scenes": [
    {{"narration": "...", "image_prompt": "..."}},
    ...
  ]
}}

SCRIPT:
{script}"""


def generate_script(theme: str, category: str) -> str:
    """Step 1 — write the long-form script."""
    print(f"[script_gen] writing script for theme: {theme[:80]}...")
    client = _client()
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SCRIPT_PROMPT.format(theme=theme, category=category)},
        ],
        temperature=0.85,
        max_tokens=6000,
    )
    script = resp.choices[0].message.content.strip()
    print(f"[script_gen] script length: {len(script.split())} words")
    return script


def break_into_scenes(script: str, n: int) -> dict:
    """Step 2 — break into N scenes with image prompts. Returns structured plan."""
    print(f"[script_gen] breaking into {n} scenes...")
    client = _client()
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a JSON-only API. You output valid JSON only. No markdown fences, no commentary."},
            {"role": "user", "content": SCENE_PROMPT.format(script=script, n=n)},
        ],
        temperature=0.4,
        max_tokens=10000,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    # strip accidental ```json fences if the model ignored the rule
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    plan = json.loads(raw)

    if "scenes" not in plan or not plan["scenes"]:
        raise RuntimeError(f"LLM returned no scenes. Raw: {raw[:500]}")
    print(f"[script_gen] got {len(plan['scenes'])} scenes, title: {plan.get('title', '?')[:60]}")
    return plan


def generate_video_plan(theme: str, category: str, n_scenes: int) -> dict:
    """Full pipeline: theme -> script -> scene plan (with metadata)."""
    script = generate_script(theme, category)
    plan = break_into_scenes(script, n_scenes)
    plan["full_script"] = script
    plan["theme"] = theme
    plan["category"] = category
    return plan


if __name__ == "__main__":
    # quick smoke test
    from themes import pick_theme
    cat, th = pick_theme()
    plan = generate_video_plan(th, cat, 3)
    print(json.dumps(plan, indent=2)[:1500])
