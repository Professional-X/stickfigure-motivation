"""Generate viral video script + scene breakdown via OpenRouter (free Nemotron Ultra).

Viral structure (built for retention, not just content):
1. PATTERN INTERRUPT OPEN — first line is a jarring mid-thought statement,
   no "hey guys", no intro. Viewer is hooked before they can scroll.
2. CONTROVERSIAL HOOK — the contrarian thesis stated hard in the first 15 sec.
3. STAY-WITH-ME PROMPTS — "stay with me here", "this is the part nobody tells
   you", "watch till the end" sprinkled every 2-3 minutes.
4. RECURRING CALLOUT — one anchor phrase repeated 3-5 times (like Goggins'
   "stay hard") that becomes the video's signature.
5. PACING SHIFTS — short 3-5 word punches mixed with longer reflective runs,
   deliberate rhythm changes every 30-60 seconds.
6. END LOOP — closing line references the opening hook, creating a loop that
   drives rewatches.

Also generates a thumbnail_text (the 3-5 bold words for the thumbnail) and a
hook_line (the exact first sentence, used as the spoken cold open).
"""
import json
import re
import time
from openai import OpenAI
import config
import svg_poses


def _client() -> OpenAI:
    if not config.LLM_API_KEY:
        raise RuntimeError(
            f"LLM_API_KEY not set for provider '{config.LLM_PROVIDER}'. "
            f"Set the appropriate env var (OPENROUTER_API_KEY or NVIDIA_API_KEY)."
        )
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


SYSTEM_PROMPT = """You are a viral YouTube ghostwriter for a men's motivation channel.

Your job is not to write "good motivation content". Your job is to write scripts that grab a viewer in the first 3 seconds, hold them through a 10-minute video, and make them rewatch the end.

You write like David Goggins crossed with Marcus Aurelius crossed with a man who has been knocked down and got back up. Sparse. Brutal. Direct. No fluff. No clichés.

BANNED WORDS (never use these — they are the fingerprints of a soft writer):
  journey, unlock, level up, best self, embrace the process, trust the journey,
  manifest, abundance, vibration, energy, gratitude practice, self-care,
  toxic, gaslighting, boundaries (in the therapy sense), healing era,
  main character energy, soft girl era, protected at all costs.

You write for men aged 18-35 who are tired of soft living. Every line should make a comfortable man uncomfortable.

You are NOT a life coach. You are a man who has been there and is telling the truth because nobody else will."""


SCRIPT_PROMPT = """Write a 10-12 minute viral motivation script for a YouTube video.

Core angle (this is the controversial hook — lean INTO it, do not soften it): {theme}
Hook style: {category}

VIRAL STRUCTURE — follow this exactly, it is not optional:

1. PATTERN INTERRUPT OPEN (first 1-2 sentences, ~15 seconds spoken):
   - Start mid-thought or with a jarring statement. No "hey", no "so", no greeting.
   - The first sentence must be impossible to scroll past.
   - Example energy: "You're not tired. You're weak." / "5am is a lie sold to broken men."
   - Do NOT explain what the video is about. Just hit them.

2. CONTROVERSIAL HOOK (first 90 seconds):
   - State the contrarian thesis hard. No hedging. No "in my opinion".
   - Back it with one concrete reason in plain language.

3. RECURRING CALLOUT (used 3-5 times across the script):
   - Pick ONE short anchor phrase (2-5 words) that becomes the video's signature.
   - Drop it at emotional peaks. Examples: "Stay hard." / "No one is coming." / "Build anyway."
   - This phrase goes in the recurring_phrase field below.

4. STAY-WITH-ME PROMPTS (every 2-3 minutes):
   - Weave in lines like: "Stay with me here." / "This is the part nobody tells you." /
     "Watch till the end — this is where it flips." / "Most men stop listening right here."
   - Do not overuse. 3-4 across the whole script.

5. PACING SHIFTS:
   - Mix 3-5 word punch sentences with longer 15-25 word reflective runs.
   - Change rhythm every 30-60 seconds. A long slow paragraph should be followed
     by a staccato burst of short sentences.

6. END LOOP (final 1-2 sentences):
   - The closing line must callback the opening hook — same words, or a direct answer to it.
   - This creates a loop that drives rewatches. If you opened with "You're not tired.
     You're weak." close with something that completes that thought.

CONTENT RULES:
- 1,600-2,000 words (about 10-12 minutes at a slow deliberate pace).
- Short paragraphs. Sentences vary between 3 and 25 words.
- Include 2-3 metaphorical turns the listener remembers a week later.
- No questions to the audience. No "you know what I mean?". Statements only.
- No timestamps, no scene directions, no [pause] markers, no emoji, no markdown, no asterisks.
- End on a single hard statement, not a question.

Write the script now. Plain text only. Hit hard from word one."""


# Pose list injected into the scene breakdown prompt so the LLM picks from
# a known set. This guarantees visual consistency — same character, just
# different poses from our hand-crafted SVG library.
POSE_LIST_TEXT = "\n".join(f"  - {name}" for name in svg_poses.POSE_NAMES)

SCENE_PROMPT = """You are breaking a viral motivation script into visual scenes for a stick-figure motivation video.

Each scene shows ONE stick-figure pose from a fixed library while the narration plays. The same character appears in every frame — only the pose changes.

CRITICAL: Each scene's narration must be 70-110 words long (about 30-45 seconds when read aloud). Do NOT split the script into tiny 1-2 sentence chunks. Group consecutive sentences into substantial narration blocks of 70-110 words each.

Given the script below, break it into {n} sequential scenes. For each scene, output:
- narration: a 70-110 word chunk of the script (verbatim from the script, in order — every word of the script must appear across all scenes with nothing added or removed)
- pose: ONE pose name from the list below. Choose the pose that best matches the emotional beat of the narration. Vary poses across scenes (don't repeat the same pose twice in a row unless intentional).

Available poses (use these EXACT names, nothing else):
{pose_list}

Pose meaning guide:
- standing_tall: resolve, presence
- walking: forward motion, daily routine
- running: urgency, intensity
- sitting_ground: defeat, contemplation
- kneeling: prayer, surrender
- looking_up: aspiration, hope
- climbing: struggle upward
- pointing_forward: direction, purpose
- pushing_boulder: Sisyphean effort
- carrying_load: burden, responsibility
- standing_alone_hill: solitude, vantage
- facing_wall: obstacle, blockage
- arms_crossed: defiance, self-containment
- falling: collapse, failure
- rising_up: getting back up
- fist_clenched: anger, resolve
- meditating: stillness, discipline
- writing: journaling, reflection
- standing_window: longing, contemplation
- staring_mirror: self-confrontation
- walking_alone_path: lonely journey
- bowing_head: humility, grief
- sun_rising: new beginning
- empty_chair: absence, loss
- clock_waiting: time pressure
- holding_light: hope, guidance
- standing_mountain_top: achievement
- face_down: total exhaustion
- two_paths: choice, decision
- arms_raised: triumph or surrender
- dark_room_alone: isolation, depression
- handshake_self: commitment to self
- looking_back: regret, reflection

ALSO generate these top-level fields (viral packaging):

- title: a YouTube title under 70 chars. Must be clickbait-grade: controversial, curiosity-gap, or brutal-truth. NO emoji. NO questions. Strong verb. Sounds like a statement that dares you not to click. Examples of the energy: "Why Waking Up At 5AM Is Destroying You" / "Discipline Is A Scam Sold To Broken Men" / "The 3AM Rule That Rewired My Brain" / "You're Not Tired. You're Weak." Title-case the important words.

- thumbnail_text: 3-6 BOLD words for the thumbnail overlay. This is what appears in huge text on the thumbnail image next to the stick figure. Must be DIFFERENT from the title (shorter, punchier, more visual). Examples: "YOU'RE WEAK" / "5AM IS A LIE" / "NO ONE IS COMING" / "BUILD ANYWAY" / "STOP SCROLLING". ALL CAPS. No punctuation except maybe one exclamation mark. Max 6 words.

- hook_line: the EXACT first sentence of the script (the pattern interrupt open). Verbatim. This gets shown as a caption on the first frame.

- recurring_phrase: the anchor phrase used 3-5 times in the script (the recurring callout). 2-5 words. Example: "Stay hard." / "No one is coming." / "Build anyway."

- description: a 150-200 word YouTube description in the same brutal tone. Must restate the controversial hook in the first line (for SEO + preview). End with a single line of 5 hashtags. No emoji.

- tags: 10 lowercase comma-separated tags as a JSON array. Include the hook style (e.g. "controversial", "brutal truth"), the topic, and broad motivation terms.

Return ONLY a valid JSON object, no markdown fences, in this exact shape:
{{
  "title": "...",
  "thumbnail_text": "...",
  "hook_line": "...",
  "recurring_phrase": "...",
  "description": "...",
  "tags": ["...", "..."],
  "scenes": [
    {{"narration": "...", "pose": "pose_name_from_list"}},
    ...
  ]
}}

SCRIPT:
{script}"""


def generate_script(theme: str, category: str) -> str:
    """Step 1 — write the long-form viral script. Retries on rate-limit / empty response.

    IMPORTANT: Nemotron Ultra is a reasoning model — without `reasoning: {enabled: false}`
    it spends ~600+ tokens on internal reasoning and may exhaust max_tokens before
    producing visible content. We pass extra_body to disable reasoning explicitly.
    """
    print(f"[script_gen] writing viral script for theme: {theme[:80]}...")
    client = _client()
    last_err = None
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": SCRIPT_PROMPT.format(theme=theme, category=category)},
                ],
                temperature=0.9,
                max_tokens=6000,
                extra_body={"reasoning": {"enabled": False}},
            )
            script = (resp.choices[0].message.content or "").strip()
            if not script:
                raise RuntimeError("LLM returned empty script")
            print(f"[script_gen] script length: {len(script.split())} words")
            return script
        except Exception as e:
            last_err = e
            print(f"[script_gen] attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"script generation failed after retries. last error: {last_err}")


def break_into_scenes(script: str, n: int) -> dict:
    """Step 2 — break into N scenes with pose names + viral packaging metadata.

    CRITICAL: Nemotron Ultra is a reasoning model — without disabling reasoning,
    it spends ~600+ tokens thinking and may produce empty content when the prompt
    is large (full script). We disable reasoning via extra_body.
    """
    print(f"[script_gen] breaking into {n} scenes...")
    client = _client()
    last_err = None
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON-only API. You output valid JSON only. No markdown fences, no commentary."},
                    {"role": "user", "content": SCENE_PROMPT.format(script=script, n=n, pose_list=POSE_LIST_TEXT)},
                ],
                temperature=0.5,
                max_tokens=16000,
                response_format={"type": "json_object"},
                extra_body={"reasoning": {"enabled": False}},
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise RuntimeError("LLM returned empty scene plan")
            # strip accidental ```json fences if the model ignored the rule
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            plan = json.loads(raw)
            if "scenes" not in plan or not plan["scenes"]:
                raise RuntimeError(f"LLM returned no scenes. Raw: {raw[:500]}")
            # Enforce scene count: LLMs sometimes return wildly different counts
            # than requested (we saw 63 returned when 25 was asked). Truncate
            # to the requested count to keep video length predictable.
            scenes = plan["scenes"]
            if len(scenes) > n:
                print(f"[script_gen] LLM returned {len(scenes)} scenes, truncating to {n}")
                plan["scenes"] = scenes[:n]
            elif len(scenes) < n:
                print(f"[script_gen] WARNING: LLM returned only {len(scenes)} scenes (asked for {n})")
            # Normalize: if scene has image_prompt instead of pose, copy it over
            # (backwards compat with old prompt style)
            for s in plan["scenes"]:
                if "pose" not in s and "image_prompt" in s:
                    s["pose"] = s["image_prompt"]
            # Backfill viral fields with safe defaults if the LLM skipped them
            plan.setdefault("thumbnail_text", "WAKE UP")
            plan.setdefault("hook_line", plan["scenes"][0]["narration"][:80] if plan["scenes"] else "")
            plan.setdefault("recurring_phrase", "Stay hard.")
            print(f"[script_gen] got {len(plan['scenes'])} scenes")
            print(f"[script_gen] title: {plan.get('title', '?')[:70]}")
            print(f"[script_gen] thumbnail_text: {plan.get('thumbnail_text', '?')}")
            print(f"[script_gen] recurring_phrase: {plan.get('recurring_phrase', '?')}")
            return plan
        except json.JSONDecodeError as e:
            last_err = e
            print(f"[script_gen] JSON parse failed (attempt {attempt + 1}): {e}")
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            last_err = e
            print(f"[script_gen] attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"scene breakdown failed after retries. last error: {last_err}")


def generate_video_plan(theme: str, category: str, n_scenes: int) -> dict:
    """Full pipeline: theme -> script -> scene plan (with viral metadata)."""
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
