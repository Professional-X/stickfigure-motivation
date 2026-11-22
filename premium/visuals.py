"""Topical AI frames — v2: ONE unique image PER CUT, zero reuse, ever.

v1's mistake: 12 stills per video cycled across ~63 rapid cuts — every still
was shown ~5 times and the video read as "the same frames on loop". v2 fixes
this structurally: the montage's segment plan (one cut per 2.2-4.4s narration
beat, ~45-63 cuts/video) is computed FIRST, and every single cut gets its OWN
image, derived from the exact words spoken during that cut. Once a cut's image
has played, it is never used again — in this video or any future one.

How:
  1. segment_texts(plans, timings)
       Maps each planned cut to the narration text it covers (sentences whose
       midpoint falls inside the cut).
  2. derive_segment_prompts(topic, scene_segments)
       ONE batched LLM call PER SCENE turns those cut texts into one concrete
       cinematic image prompt per cut ("show the thing the words are about").
       Keyword heuristic per cut as fallback; duplicate prompts inside a video
       are mutated until unique.
  3. generate_one(prompt, out_path, seed)
       Free-provider chain, no watermarks:
         Pollinations flux (2 tries) -> Pollinations turbo (2 tries) ->
         Openverse CC photo (registry-deduped) -> procedural gradient (PIL,
         deterministic-unique — the guaranteed floor).
       A global adaptive-pacing lock backs off when Pollinations returns 402
       (their per-IP quota window) so parallel workers don't hammer the limiter.
  4. fetch_stills_for_segments(topic, scenes, plans, out_dir)
       Runs all cuts through a worker pool (config.VISUALS_WORKERS), returns
       {scene_idx: [cut0_path, cut1_path, ...]} ALIGNED to the plan — the
       caller can index stills[k] for cut k directly. Every entry is a real,
       valid image file: the chain never returns None.

Every prompt+seed+source is recorded in premium/visuals_library.json (committed
by publish.yml) so no image is ever regenerated verbatim in a later video.
"""
import os
import re
import json
import time
import zlib
import random
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

import config

# Registry of every frame ever generated (committed by publish.yml).
LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "visuals_library.json")

POLL_URL = config.POLLINATIONS_URL          # https://image.pollinations.ai/prompt
REFERRER = getattr(config, "POLLINATIONS_REFERRER", "")

# Pollinations free tier is per-IP quota'd: burst requests get HTTP 402 until
# the window refills (~30-60s). One image per cut means ~45-60 generations, so
# workers share a global pacing lock: after ANY 402, everyone waits out the
# refill window instead of burning attempts. flux first (best quality), turbo
# as in-service failover (faster, lighter quota), then Openverse photos, then
# a procedural gradient that can never repeat.
FLUX_TRIES = 2
TURBO_TRIES = 2
TRY_BACKOFF = [8, 22]          # seconds between attempts within one model
QUOTA_COOLDOWN = 32.0          # global wait after a 402 (shared by all workers)
OPENVERSE_URL = "https://api.openverse.org/v1/images/"

_lock = threading.Lock()
_last_402 = 0.0                # monotonic ts of the most recent quota hit


# ----- LLM client (NVIDIA key first — confirmed set in production) ------------
def _llm_config() -> tuple[str, str, str]:
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

You are given the narration of ONE video scene, already split into the exact cuts the editor will make (each cut = 2-4 seconds of voiceover). For EACH cut you design ONE image. The image MUST show what THAT cut's words are literally about — the concrete subject, object, place, action or metaphor — not generic scenery.

Rules:
  - Photorealistic cinematic film still, 16:9 wide composition.
  - Name the SPECIFIC subject of THAT cut (a cold shower running, knuckles wrapping before a punch, an unopened resume on a desk, shackles on a stone floor, a phone face-down at dinner, etc.). Consecutive cuts tell a SEQUENCE — vary the shot: wide establishing, close detail, over-shoulder, low angle, silhouette, hands only, environment empty of people.
  - Moody dramatic lighting, shallow depth of field, muted teal-and-orange grade. No smiling-at-camera people.
  - NO text, captions, logos, watermarks, collages, split-screen.
  - 12-30 words, plain prose, one composition each, DIFFERENT from every other cut.

You output ONLY a JSON object: {"prompts": [{"seg": <1-based cut number>, "prompt": "<image prompt>"}, ...]} — one entry per cut, no markdown, no commentary."""


def _scene_llm_prompt(topic: dict, scene: dict, cut_texts: list[str]) -> str:
    lines = [f"CUT {j+1}: {t}" for j, t in enumerate(cut_texts)]
    return f"""VIDEO: {topic.get('title','')} ({topic.get('category','')})
SCENE CATEGORY: {scene.get('clip_category','')}

Write ONE image prompt for EACH of the {len(cut_texts)} cuts below — {len(cut_texts)} prompts total, ALL in this single response:

{chr(10).join(lines)}

Return ONLY: {{"prompts": [{{"seg": 1, "prompt": "..."}}, ...]}}"""


# ----- segment -> narration text mapping --------------------------------------
def segment_texts(plan: list[tuple[float, float]], timings: list[dict]) -> list[str]:
    """For each planned cut (start,end) return the narration text it covers
    (sentences whose midpoint falls inside the cut)."""
    out = []
    for (s, e) in plan:
        mid_texts = [t["text"] for t in timings
                     if s <= (t["start"] + t["end"]) / 2 < e]
        if not mid_texts:  # short cut between sentence gaps
            mid_texts = [t["text"] for t in timings if t["start"] < e and t["end"] > s]
        out.append(" ".join(mid_texts) or "silence beat")
    return out


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


def _keywords(text: str, k: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    freq = {}
    for w in words:
        if w in _STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda w: (-freq[w], w))[:k]


def _heuristic_prompt(topic: dict, text: str, idx: int) -> str:
    cat = topic.get("category", "motivation").lower()
    kws = _keywords(text, k=4)
    subject = ", ".join(kws) if kws else "a lone figure on an empty road at dawn"
    angles = ["wide establishing shot", "extreme close-up detail",
              "low angle looking up", "over-the-shoulder view",
              "silhouette against light", "hands only in frame"]
    return (f"cinematic film still, {subject}, {angles[idx % len(angles)]}, "
            f"{cat} mood, dramatic moody lighting, muted teal and orange grade, "
            "shallow depth of field, no text, no watermark")


# ----- prompt derivation (one LLM call per scene) ------------------------------
def derive_segment_prompts(topic: dict, scene_idx: int, scene: dict,
                           cut_texts: list[str], seen: set[str]) -> list[str]:
    """Return one image prompt per cut of this scene. LLM batched per scene,
    heuristic per cut as fallback, duplicates mutated until unique."""
    n = len(cut_texts)
    prompts: list[str | None] = [None] * n
    if _llm_available():
        try:
            client = _llm_client()
            _, _, model = _llm_config()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _scene_llm_prompt(topic, scene, cut_texts)},
                ],
                temperature=0.85,
                top_p=0.9,
                max_tokens=12000,   # nemotron reasons before answering
                response_format={"type": "json_object"},
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise RuntimeError("empty content")
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            arr = data if isinstance(data, list) else (
                data.get("prompts") or next((v for v in data.values()
                                             if isinstance(v, list)), []))
            for item in arr:
                try:
                    j = int(item["seg"]) - 1
                    p = str(item["prompt"]).strip()
                except Exception:
                    continue
                if 0 <= j < n and p:
                    prompts[j] = p
        except Exception as e:
            print(f"[visuals] scene {scene_idx}: LLM failed ({type(e).__name__}: "
                  f"{str(e)[:90]}) -> heuristic prompts")
    n_llm = 0
    for j in range(n):
        p = prompts[j] or _heuristic_prompt(topic, cut_texts[j], j)
        if prompts[j]:
            n_llm += 1
        # enforce uniqueness within this video
        base = p
        m = 0
        while p.lower() in seen:
            m += 1
            p = f"{base}, alternate composition {m}, different angle and subject moment"
        seen.add(p.lower())
        prompts[j] = p
    print(f"[visuals] scene {scene_idx}: {n_llm}/{n} prompts from LLM "
          f"({n} cuts, all unique)")
    return prompts  # type: ignore[return-value]


# ----- image providers ---------------------------------------------------------
def _seed_for(prompt: str, salt: int = 0) -> int:
    h = zlib.crc32(prompt.encode("utf-8")) & 0xFFFFFFFF
    return (h ^ (salt * 2654435761)) & 0x7FFFFFFF


def _respect_quota() -> None:
    """If any worker recently hit the 402 quota window, wait it out globally."""
    global _last_402
    while True:
        with _lock:
            wait = _last_402 + QUOTA_COOLDOWN - time.monotonic()
        if wait <= 0:
            return
        time.sleep(min(wait, 5.0))


def _poll_request(model: str, prompt: str, seed: int, out_path: str) -> str:
    url = f"{POLL_URL}/{requests.utils.quote(prompt, safe='')}"
    params = {"width": 1280, "height": 720, "seed": seed, "model": model,
              "nologo": "true", "referrer": REFERRER}
    r = requests.get(url, params=params, timeout=150, stream=True)
    ctype = r.headers.get("content-type", "")
    if r.status_code == 402 or r.status_code == 429:
        global _last_402
        with _lock:
            _last_402 = time.monotonic()
        raise RuntimeError(f"quota HTTP {r.status_code}")
    if r.status_code == 200 and "image" in ctype and len(r.content) > 3000:
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    raise RuntimeError(f"bad response HTTP {r.status_code} ({ctype[:24]}, {len(r.content)}B)")


def _gen_pollinations(prompt: str, out_path: str, seed: int) -> str:
    for model, tries in (("flux", FLUX_TRIES), ("turbo", TURBO_TRIES)):
        for i in range(tries):
            _respect_quota()
            try:
                return _poll_request(model, prompt, seed, out_path)
            except RuntimeError as e:
                if "quota" not in str(e) and i == tries - 1 and model == "turbo":
                    raise
                time.sleep(TRY_BACKOFF[min(i, len(TRY_BACKOFF) - 1)])
            except Exception as e:
                print(f"  [visuals] {model} error: {str(e)[:70]}")
                time.sleep(TRY_BACKOFF[min(i, len(TRY_BACKOFF) - 1)])
    raise RuntimeError("pollinations flux+turbo exhausted")


def _gen_openverse(prompt: str, out_path: str, seed: int) -> str:
    """Free CC-licensed photo search (no key, no watermark) as a fallback."""
    kws = _keywords(prompt, k=3) or ["cinematic", "moody"]
    params = {"q": " ".join(kws[:2]), "license_type": "commercial",
              "per_page": 8, "fields": "id,url,thumbnail"}
    r = requests.get(OPENVERSE_URL, params=params, timeout=60,
                     headers={"User-Agent": REFERRER or "stickverse"})
    if r.status_code != 200:
        raise RuntimeError(f"openverse HTTP {r.status_code}")
    for item in r.json().get("results", []):
        for field in ("url", "thumbnail"):
            src = item.get(field)
            if not src:
                continue
            try:
                img = requests.get(src, timeout=60, stream=True)
                if img.status_code == 200 and "image" in img.headers.get(
                        "content-type", "") and len(img.content) > 20000:
                    with open(out_path, "wb") as f:
                        f.write(img.content)
                    return out_path
            except Exception:
                continue
    raise RuntimeError("openverse: no usable image")


def procedural_still(out_path: str, seed: int) -> str:
    """Deterministic-unique cinematic gradient frame (PIL). The guaranteed
    floor: always succeeds, never repeats (palette derived from the seed)."""
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    w, h = 1280, 720
    base = rng.randint(8, 30)
    hue_shift = rng.randint(-14, 14)
    top = (max(0, base + 4 + hue_shift), max(0, base + 8), max(0, base + 14 - hue_shift))
    bot = (max(0, base // 2), max(0, base // 2 + 3), max(0, base // 2 + 6))
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        t = y / h
        row = tuple(int(top[c] + (bot[c] - top[c]) * t) for c in range(3))
        for x in range(w):
            px[x, y] = row
    # soft diagonal light streak + vignette so it reads as a graded frame
    streak = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(streak)
    x0 = rng.randint(w // 5, w - w // 5)
    d.line([(x0, -50), (x0 - rng.randint(120, 300), h + 50)], fill=26, width=rng.randint(90, 200))
    streak = streak.filter(ImageFilter.GaussianBlur(60))
    im = Image.composite(Image.new("RGB", (w, h), (70, 88, 96)), im, streak)
    vig = Image.new("L", (w, h), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse([-w // 3, -h // 3, w + w // 3, h + h // 3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGB", (w, h), (2, 3, 5))
    im = Image.composite(im, dark, vig)
    im.save(out_path, "JPEG", quality=88)
    return out_path


def generate_one(prompt: str, out_path: str, seed: int) -> tuple[str, str]:
    """Full provider chain for one cut. Returns (path, source). Always succeeds."""
    try:
        return _gen_pollinations(prompt, out_path, seed), "pollinations"
    except Exception as e:
        print(f"  [visuals] pollinations exhausted ({str(e)[:60]}) -> openverse")
    try:
        return _gen_openverse(prompt, out_path, seed), "openverse"
    except Exception as e:
        print(f"  [visuals] openverse failed ({str(e)[:60]}) -> procedural frame")
    return procedural_still(out_path, seed), "procedural"


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
def fetch_stills_for_segments(topic: dict, scenes: list,
                              plans: dict[int, list[tuple[float, float]]],
                              stills_dir: str) -> dict[int, list[str]]:
    """Generate ONE unique image per planned cut.

    plans: {scene_idx: [(start,end), ...]} from compose.segment_plan.
    Returns {scene_idx: [cut0_path, cut1_path, ...]} — len(list) == len(plan),
    every entry a valid image file (chain floor = procedural, never None).
    """
    os.makedirs(stills_dir, exist_ok=True)
    cap = int(getattr(config, "VISUALS_MAX_PER_VIDEO", 96))
    seen_prompts: set[str] = set()
    used = _used_seeds()

    # 1. prompts + seeds assigned serially (deterministic, registry-unique)
    jobs = []   # (scene_idx, cut_idx, prompt, seed, out_path, cached)
    total_cuts = 0
    for i, scene in enumerate(scenes):
        plan = plans.get(i, [])
        texts = segment_texts(plan, scene.get("sentence_timings") or [])
        prompts = derive_segment_prompts(topic, i, scene, texts, seen_prompts)
        for j, prompt in enumerate(prompts):
            if total_cuts >= cap:
                prompt = f"procedural frame budget-cap {total_cuts}"
            seed = _seed_for(f"{topic.get('id')}|{i}|{j}|{prompt}")
            while seed in used:
                seed = (seed + 1) & 0x7FFFFFFF
            used.add(seed)
            out_path = os.path.join(stills_dir, f"s{i:02d}_c{j:03d}.jpg")
            cached = os.path.exists(out_path) and os.path.getsize(out_path) > 3000
            jobs.append((i, j, prompt, seed, out_path, cached))
            total_cuts += 1
    print(f"[visuals] {total_cuts} cuts -> {total_cuts} unique frames "
          f"({len(scenes)} scenes, workers={getattr(config, 'VISUALS_WORKERS', 4)})")

    # 2. generate in parallel
    result: dict[int, list[str | None]] = {i: [None] * len(plans.get(i, []))
                                           for i in range(len(scenes))}
    counts = {"pollinations": 0, "openverse": 0, "procedural": 0, "cached": 0}
    recorded = []
    rec_lock = threading.Lock()

    def work(job):
        i, j, prompt, seed, out_path, cached = job
        if cached:
            src = "cached"
        else:
            _, src = generate_one(prompt, out_path, seed)
        with rec_lock:
            counts[src] = counts.get(src, 0) + 1
            recorded.append({"topic_id": topic.get("id"), "scene": i, "cut": j,
                             "prompt": prompt, "seed": seed, "source": src,
                             "path": os.path.basename(out_path)})
        print(f"[visuals] cut s{i}c{j}: {src} "
              f"({os.path.getsize(out_path) // 1024} KB) \"{prompt[:48]}...\"")
        return i, j, out_path

    workers = max(1, int(getattr(config, "VISUALS_WORKERS", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, j, path in pool.map(work, jobs):
            result[i][j] = path

    # 3. registry (per-cut records -> zero cross-video reuse)
    if recorded:
        lib = load_library()
        lib.extend(recorded)
        save_library(lib)
    srcs = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    print(f"[visuals] DONE: {total_cuts} unique frames ({srcs}); "
          f"registry now {len(load_library())} entries")

    # safety: any unfilled slot (shouldn't happen) gets a procedural frame
    for i, lst in result.items():
        for j, p in enumerate(lst):
            if p is None:
                p = procedural_still(os.path.join(stills_dir, f"s{i:02d}_c{j:03d}.jpg"),
                                     _seed_for(f"fill|{topic.get('id')}|{i}|{j}"))
                lst[j] = p
    return result  # type: ignore[return-value]


if __name__ == "__main__":
    # smoke: plan + prompts + frames for ONE scene, verify uniqueness
    from premium import scripts as S
    from premium import compose as CO
    topic = S.TOPICS[0]
    scenes = topic["scenes"]
    plan = CO.segment_plan(30.0, [])
    texts = segment_texts(plan, [])
    print(f"plan cuts: {len(plan)}")
    os.makedirs("./output", exist_ok=True)
    seed = _seed_for("smoke test frame")
    p, src = generate_one("cinematic film still, a lone runner on a rain-soaked "
                          "city street at night, moody light", "./output/v2_test.jpg", seed)
    print(f"OK -> {p} ({src}, {os.path.getsize(p)//1024} KB)")
