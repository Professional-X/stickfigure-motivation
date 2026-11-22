"""Topical AI-generated scene stills — the "show the THING the script is about" system.

This replaces the old generic Mixkit stock footage (mountains/city/sea/sky
categories → "random sunset, random mountain" that had nothing to do with the
script) with UNIQUE, watermark-free stills generated on demand from each
scene's actual narration.

Pipeline:
  1. derive_scene_prompts(topic, scenes, per_scene)
       ONE batched LLM call (same OpenRouter/NVIDIA client the script generator
       uses) turns each scene's narration into `per_scene` distinct cinematic
       image prompts that depict what the words are actually about. Falls back
       to a keyword heuristic if the LLM is unavailable, so the pipeline never
       blocks on LLM availability.
  2. generate_still(prompt, out_path, seed)
       Pollinations (free, no auth, no watermark) by default, or Cloudflare
       Workers AI if configured. The seed is derived from the prompt itself, so
       every (topic, scene, variant) gets a deterministic-but-globally-unique
       image that is never regenerated verbatim.
  3. fetch_stills_for_scenes(topic, scenes, stills_dir, per_scene)
       Generates `per_scene` stills per scene, returns {scene_idx: [paths]},
       and records every prompt+seed in premium/visuals_library.json so no
       visual is ever reused across videos (the registry is committed by
       publish.yml alongside topics_library.json).

The stills are rendered into motion by premium/compose.py (Ken Burns zoom/pan
+ cinematic grade), alternated across each scene's rapid-cut segments so no
two consecutive cuts share the same frame. Viewers now see content that
matches the script instead of looping generic B-roll.

All imagery is free + non-watermarked: Pollinations flux is free with no
attribution; Cloudflare Workers AI is free up to 10k neurons/day.
"""
import os
import re
import json
import time
import zlib
import random
import requests

import config

# Registry of every still ever generated, so prompts/seeds never repeat across
# videos. Committed to the repo by publish.yml (same pattern as topics_library).
LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "visuals_library.json")

# Pollinations: free, no auth. flux returns a fixed 1024x576 (it ignores the
# width/height query params); compose.py lanczos-upscales to 1920x1080.
POLL_URL = config.POLLINATIONS_URL
POLL_MODEL = config.POLLINATIONS_MODEL  # 'flux' | 'turbo'

# Modest spacing between Pollinations calls (free tier rate-limits sustained
# bursts). Retry-with-backoff handles the rare 429, so this can stay small.
CALL_DELAY = 6.0
MAX_ATTEMPTS = 4
RATE_BACKOFF = 25.0  # seconds to wait after a 429 / empty response


# ----- LLM client (prefers the NVIDIA key generate.py uses — confirmed set in
# production; falls back to the OpenRouter config if NVIDIA_API_KEY is absent) ----
def _llm_config() -> tuple[str, str, str]:
    """Return (api_key, base_url, model) for whichever LLM provider is available."""
    nkey = getattr(config, "NVIDIA_API_KEY", "") or os.environ.get("NVIDIA_API_KEY") or ""
    if nkey:
        return nkey, config.NVIDIA_BASE_URL, config.NVIDIA_MODEL
    okey = getattr(config, "LLM_API_KEY", "") or ""
    if okey:
        return okey, config.LLM_BASE_URL, config.LLM_MODEL
    return "", "", ""


def _llm_available() -> bool:
    return bool(_llm_config()[0])


def _llm_client():
    from openai import OpenAI
    key, base_url, _ = _llm_config()
    return OpenAI(base_url=base_url, api_key=key)


SYSTEM_PROMPT = """You are the art director for @StickVerse, a cinematic stoic/discipline motivation channel.

For each scene of a script you are given, you design DISTINCT visual concepts for the still images that will appear behind the narration. The image MUST depict what the scene is literally talking about — the concrete subject, object, place, action or metaphor in the words — NOT generic pretty scenery.

Rules for every prompt:
  - Photorealistic cinematic film still, 16:9 wide composition.
  - Name the SPECIFIC subject tied to the narration (a cold shower, an unmade bed at 6am, a lone climber on a switchback, a half-finished manuscript, a mirror, a stopwatch, a withered leaf, a packed gym bag, etc.). Never default to "mountains at sunset" or "waves on a beach" unless the words actually call for them.
  - Moody dramatic lighting, shallow depth of field, muted teal-and-orange grade, sense of weight or solitude. No people smiling at cameras.
  - NO text, NO captions, NO logos, NO watermarks, NO collages, NO split-screen.
  - One composition per prompt. 12-30 words. Plain prose, no markdown.
  - Each prompt in a scene must be a DIFFERENT composition (different angle/subject moment), not a rephrase.

You output ONLY a JSON object of the EXACT shape: {"prompts": [{"scene": <1-based>, "variant": <1-based>, "prompt": "<image prompt>"}, ...]}. No markdown fences, no commentary, no reasoning."""


def _user_prompt(topic: dict, scenes: list, per_scene: int) -> str:
    scene_lines = []
    for i, s in enumerate(scenes):
        scene_lines.append(f"SCENE {i+1} ({s.get('clip_category','')}): {s['narration']}")
    total = per_scene * len(scenes)
    return f"""VIDEO TITLE: {topic.get('title','')}
CATEGORY: {topic.get('category','')}

Write EXACTLY {per_scene} distinct image prompts for EACH of the {len(scenes)} scenes — {total} prompts total, ALL in this single response. Every prompt must depict what THAT scene's narration is about.

{chr(10).join(scene_lines)}

Return ONLY this JSON object (fill the array with all {total} objects, ordered by scene then variant):
{{"prompts": [{{"scene": 1, "variant": 1, "prompt": "..."}}, ...]}}"""


def derive_scene_prompts(topic: dict, scenes: list, per_scene: int = 2) -> list[dict]:
    """Return [{scene (0-based), variant (0-based), prompt}, ...] length len(scenes)*per_scene.

    One batched LLM call for the whole video. On any failure, falls back to a
    keyword heuristic derived from each scene's narration so the pipeline still
    gets topical, unique prompts without an LLM.
    """
    if not _llm_available():
        print("[visuals] no LLM key -> heuristic prompts")
        return _heuristic_prompts(topic, scenes, per_scene)
    try:
        client = _llm_client()
        _, _, model = _llm_config()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(topic, scenes, per_scene)},
            ],
            temperature=0.8,
            top_p=0.9,
            max_tokens=12000,  # nemotron is a reasoning model — needs headroom for
                               # reasoning_content before it emits all 12 prompts
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            raise RuntimeError("empty content (reasoning consumed the budget)")
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        # expected shape: {"prompts": [...]} ; also tolerate a bare array or
        # any single list-valued key the model might wrap it under
        if isinstance(data, list):
            arr = data
        elif isinstance(data, dict):
            arr = data.get("prompts") or next(
                (v for v in data.values() if isinstance(v, list)), [])
        else:
            arr = []
        out = []
        for item in arr:
            try:
                scene = int(item["scene"]) - 1
                variant = int(item.get("variant", 1)) - 1
                prompt = str(item["prompt"]).strip()
            except Exception:
                continue
            if 0 <= scene < len(scenes) and prompt:
                out.append({"scene": scene, "variant": variant,
                            "prompt": prompt, "_llm": True})
        # fill any missing (scene,variant) slots from the heuristic
        have = {(o["scene"], o["variant"]) for o in out}
        for o in _heuristic_prompts(topic, scenes, per_scene, verbose=False):
            if (o["scene"], o["variant"]) not in have:
                out.append(o)
                have.add((o["scene"], o["variant"]))
        out.sort(key=lambda o: (o["scene"], o["variant"]))
        n_llm = sum(1 for o in out if o.get("_llm"))
        print(f"[visuals] LLM derived {len(out)} topical prompts "
              f"({n_llm} from LLM, {len(out)-n_llm} heuristic fill; "
              f"{len(scenes)} scenes x {per_scene})")
        return out
    except Exception as e:
        print(f"[visuals] LLM prompt derivation failed ({type(e).__name__}: {str(e)[:120]}) -> heuristic")
        return _heuristic_prompts(topic, scenes, per_scene)


_STOPWORDS = {
    "the","a","an","and","or","but","of","to","in","on","at","for","with","by",
    "is","are","was","were","be","been","being","it","its","you","your","they",
    "their","them","he","she","his","her","we","our","us","i","my","me","this",
    "that","these","those","not","no","do","does","did","done","have","has","had",
    "will","would","can","could","should","than","then","so","as","if","when",
    "what","which","who","whom","whose","from","into","out","up","down","over",
    "about","because","while","also","just","only","more","most","less","very",
    "one","two","every","each","all","any","some","such","same","other","again",
}


def _keywords(text: str, k: int = 6) -> list[str]:
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    freq = {}
    for w in words:
        if w in _STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: (-freq[w], w))
    return ranked[:k]


def _heuristic_prompts(topic: dict, scenes: list, per_scene: int,
                       verbose: bool = True) -> list[dict]:
    """Keyword-derived prompts when the LLM is unavailable. Less poetic but
    still topical (depicts words from the actual narration) and unique per
    scene thanks to the per-scene keyword extraction + seed."""
    cat = topic.get("category", "motivation").lower()
    out = []
    for i, s in enumerate(scenes):
        kws = _keywords(s["narration"], k=5 + per_scene)
        for v in range(per_scene):
            pick = kws[v * 2:v * 2 + 4] or kws[:4]
            subject = ", ".join(pick) if pick else "a lone figure, an empty road, dawn light"
            out.append({
                "scene": i,
                "variant": v,
                "prompt": (f"cinematic film still, {subject}, {cat} mood, "
                           "dramatic moody lighting, muted teal and orange grade, "
                           "wide composition, shallow depth of field, no text, no watermark"),
            })
    if verbose:
        print(f"[visuals] heuristic prompts: {len(out)} ({len(scenes)} scenes x {per_scene})")
    return out


# ----- image generation -------------------------------------------------------
def _seed_for(prompt: str, salt: int = 0) -> int:
    """Deterministic seed from the prompt text (+ optional salt). Same prompt
    + salt -> same image; different prompts -> different images."""
    h = zlib.crc32(prompt.encode("utf-8")) & 0xFFFFFFFF
    return (h ^ (salt * 2654435761)) & 0x7FFFFFFF


def _generate_pollinations(prompt: str, out_path: str, seed: int) -> str:
    url = f"{POLL_URL}/{requests.utils.quote(prompt, safe='')}"
    params = {"width": 1280, "height": 720, "seed": seed,
              "model": POLL_MODEL, "nologo": "true"}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(url, params=params, timeout=120, stream=True)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and "image" in ctype:
                data = r.content
                if len(data) > 3000:  # real image, not a tiny error stub
                    with open(out_path, "wb") as f:
                        f.write(data)
                    return out_path
            print(f"  [visuals] pollinations attempt {attempt}: HTTP {r.status_code} "
                  f"({ctype[:30]}, {len(r.content)}B) -> retry in {RATE_BACKOFF}s")
        except Exception as e:
            print(f"  [visuals] pollinations attempt {attempt} error: {str(e)[:80]}")
        time.sleep(RATE_BACKOFF * attempt)
    raise RuntimeError(f"pollinations failed after {MAX_ATTEMPTS} attempts")


def _generate_cloudflare(prompt: str, out_path: str, seed: int) -> str:
    url = config.CLOUDFLARE_FLUX_URL
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}",
                 "Content-Type": "application/json"},
        json={"prompt": prompt, "seed": seed, "steps": 4},
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"cloudflare HTTP {r.status_code}: {r.text[:120]}")
    data = r.json().get("result", {}).get("image")
    if not data:
        raise RuntimeError("cloudflare returned no image")
    # CF returns base64 image bytes
    import base64
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data))
    return out_path


def generate_still(prompt: str, out_path: str, seed: int) -> str:
    """Generate one still. Provider chosen by config.IMAGE_PROVIDER."""
    provider = (config.IMAGE_PROVIDER or "pollinations").lower()
    if provider == "cloudflare" and config.CLOUDFLARE_API_TOKEN:
        try:
            return _generate_cloudflare(prompt, out_path, seed)
        except Exception as e:
            print(f"  [visuals] cloudflare failed ({str(e)[:80]}) -> pollinations fallback")
    return _generate_pollinations(prompt, out_path, seed)


# ----- registry ---------------------------------------------------------------
def load_library(path: str = LIBRARY_PATH) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_library(entries: list, path: str = LIBRARY_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _used_seeds(path: str = LIBRARY_PATH) -> set:
    return {e.get("seed") for e in load_library(path) if isinstance(e, dict)}


# ----- orchestrator -----------------------------------------------------------
def fetch_stills_for_scenes(topic: dict, scenes: list, stills_dir: str,
                            per_scene: int = 2, seed_salt: int = 0) -> dict:
    """Generate `per_scene` unique topical stills per scene.

    Returns {scene_idx: [still_path,...]} with exactly `per_scene` paths per
    scene where generation succeeded (fewer on partial failure; empty list if
    the scene fully failed so the caller can Mixkit-fallback just that scene).

    `seed_salt` lets a re-run of the SAME topic produce fresh visuals (the
    queue normally serves fresh topics, so the default 0 is fine; pass a
    run-counter to force novelty on a deliberate re-publish).
    """
    os.makedirs(stills_dir, exist_ok=True)
    prompts = derive_scene_prompts(topic, scenes, per_scene)
    used = _used_seeds()

    result: dict[int, list[str]] = {i: [] for i in range(len(scenes))}
    recorded = []
    last_call = 0.0
    ok = 0
    for p in prompts:
        si, vi = p["scene"], p["variant"]
        seed = _seed_for(p["prompt"], salt=seed_salt)
        # guarantee global uniqueness: bump seed until it's unused
        while seed in used:
            seed = (seed + 1) & 0x7FFFFFFF
        out_path = os.path.join(stills_dir, f"scene_{si:02d}_v{vi}.jpg")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 3000:
            # cached from a prior partial run — reuse, still record it
            result[si].append(out_path)
            used.add(seed)
            recorded.append({"topic_id": topic.get("id"), "scene": si,
                             "variant": vi, "prompt": p["prompt"],
                             "seed": seed, "path": os.path.basename(out_path)})
            ok += 1
            continue
        # pace the free-tier rate limiter
        gap = time.time() - last_call
        if gap < CALL_DELAY:
            time.sleep(CALL_DELAY - gap)
        last_call = time.time()
        try:
            generate_still(p["prompt"], out_path, seed)
            result[si].append(out_path)
            used.add(seed)
            recorded.append({"topic_id": topic.get("id"), "scene": si,
                             "variant": vi, "prompt": p["prompt"],
                             "seed": seed, "path": os.path.basename(out_path)})
            ok += 1
            print(f"[visuals] scene {si} v{vi}: {os.path.getsize(out_path)//1024} KB "
                  f"(seed {seed})")
        except Exception as e:
            print(f"[visuals] scene {si} v{vi} FAILED ({str(e)[:90]}) -> Mixkit will cover it")

    if recorded:
        lib = load_library()
        lib.extend(recorded)
        save_library(lib)
        print(f"[visuals] generated {ok}/{len(prompts)} stills; registry now "
              f"{len(lib)} entries")

    # order each scene's stills by variant so alternation is deterministic
    for si in result:
        result[si].sort()
    return result


if __name__ == "__main__":
    # smoke test: derive prompts + generate ONE still for the first scene of
    # the first curated topic, using the heuristic path if no LLM key.
    from premium import scripts as S
    topic = S.TOPICS[0]
    scenes = topic["scenes"]
    prompts = derive_scene_prompts(topic, scenes, per_scene=2)
    for p in prompts:
        print(f"  scene {p['scene']} v{p['variant']}: {p['prompt'][:90]}")
    os.makedirs("./output", exist_ok=True)
    seed = _seed_for(prompts[0]["prompt"])
    generate_still(prompts[0]["prompt"], "./output/visual_test.jpg", seed)
    print(f"OK -> ./output/visual_test.jpg ({os.path.getsize('./output/visual_test.jpg')//1024} KB)")
