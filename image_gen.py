"""Generate stick-figure stills.

Default provider: Pollinations.ai (free, no API key, ~1 req/45s rate limit).
Optional: Cloudflare Workers AI (free 10k neurons/day, much faster, needs signup).
Legacy: NVIDIA Build Flux (kept for reference, most accounts aren't entitled).
"""
import os
import time
import urllib.parse
import requests
import config


def generate_image(prompt: str, out_path: str, seed: int | None = None) -> str:
    """Generate one image and save to out_path. Returns out_path."""
    if seed is None:
        seed = config.IMAGE_SEED

    if config.IMAGE_PROVIDER == "cloudflare":
        return _generate_cloudflare(prompt, out_path, seed)
    if config.IMAGE_PROVIDER == "nvidia":
        return _generate_nvidia(prompt, out_path, seed)
    return _generate_pollinations(prompt, out_path, seed)


def _generate_pollinations(prompt: str, out_path: str, seed: int) -> str:
    """Pollinations.ai — free, no auth. ~1 req / 45s rate limit on free tier.

    Uses URL-encoded GET request. Returns JPEG. We sleep POLLINATIONS_DELAY
    between calls (handled in pipeline.py) to stay under the rate limit.

    On 402 (rate limit) or 5xx, we wait the indicated time and retry.
    """
    params = {
        "width": str(config.IMAGE_WIDTH),
        "height": str(config.IMAGE_HEIGHT),
        "seed": str(seed),
        "nologo": "true",
        "model": config.POLLINATIONS_MODEL,
    }
    encoded_prompt = urllib.parse.quote(prompt, safe="")
    url = f"{config.POLLINATIONS_URL}/{encoded_prompt}?{urllib.parse.urlencode(params)}"

    last_err = None
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=180)

            if r.status_code == 200:
                ctype = r.headers.get("content-type", "")
                if "image" not in ctype:
                    last_err = f"unexpected content-type: {ctype}, body: {r.text[:200]}"
                    print(f"[image_gen] {last_err}")
                    time.sleep(15)
                    continue
                with open(out_path, "wb") as f:
                    f.write(r.content)
                print(f"[image_gen] saved {out_path} ({len(r.content) // 1024} KB)")
                return out_path

            if r.status_code == 402:
                # Free-tier rate limit. Pollinations tells us how long to wait.
                wait = config.POLLINATIONS_DELAY
                try:
                    data = r.json()
                    msg = data.get("error", {}).get("message", "")
                    # parse "Retry after Ns" out of the message
                    import re
                    m = re.search(r"Retry after (\d+)s", msg)
                    if m:
                        wait = int(m.group(1)) + 3
                except Exception:
                    pass
                print(f"[image_gen] rate-limited (402), waiting {wait}s... (attempt {attempt + 1})")
                time.sleep(wait)
                continue

            if r.status_code in (429, 500, 502, 503, 504, 522, 524):
                wait = 30 + 10 * attempt
                print(f"[image_gen] HTTP {r.status_code}, backing off {wait}s... (attempt {attempt + 1})")
                time.sleep(wait)
                continue

            # Other errors — log and retry with backoff
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            print(f"[image_gen] {last_err}")
            time.sleep(15)

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[image_gen] attempt {attempt + 1} exception: {last_err}")
            time.sleep(15)

    raise RuntimeError(
        f"Pollinations image gen failed after retries. prompt: {prompt[:80]}... last error: {last_err}"
    )


def _generate_cloudflare(prompt: str, out_path: str, seed: int) -> str:
    """Cloudflare Workers AI — Flux-1-schnell. Free 10k neurons/day (~2000 images).

    Much faster than Pollinations, no rate limit, but requires Cloudflare signup.
    Sign up at https://dash.cloudflare.com → Workers AI → get account ID + API token.
    """
    if not config.CLOUDFLARE_API_TOKEN or not config.CLOUDFLARE_ACCOUNT_ID:
        raise RuntimeError(
            "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set "
            "when IMAGE_PROVIDER=cloudflare"
        )

    headers = {
        "Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "seed": seed,
        "steps": 4,  # schnell default — fast, good quality
    }

    last_err = None
    for attempt in range(5):
        try:
            r = requests.post(config.CLOUDFLARE_FLUX_URL, headers=headers, json=payload, timeout=180)

            if r.status_code == 200:
                data = r.json()
                # Cloudflare returns {"result": {"image": <base64>, "response_type": "image/png"}}
                if not data.get("success", True):
                    last_err = f"API success=false: {data}"
                    print(f"[image_gen] {last_err}")
                    time.sleep(10)
                    continue
                result = data.get("result", {})
                image_b64 = result.get("image")
                if not image_b64:
                    last_err = f"no image in response: {str(data)[:300]}"
                    print(f"[image_gen] {last_err}")
                    time.sleep(10)
                    continue
                import base64
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                print(f"[image_gen] saved {out_path} ({os.path.getsize(out_path) // 1024} KB)")
                return out_path

            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"[image_gen] rate-limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue

            last_err = f"HTTP {r.status_code}: {r.text[:300]}"
            print(f"[image_gen] {last_err}")
            time.sleep(15)

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[image_gen] attempt {attempt + 1} exception: {last_err}")
            time.sleep(15)

    raise RuntimeError(
        f"Cloudflare image gen failed after retries. prompt: {prompt[:80]}... last error: {last_err}"
    )


def _generate_nvidia(prompt: str, out_path: str, seed: int) -> str:
    """Legacy NVIDIA Build Flux endpoint. Most accounts aren't entitled."""
    import base64
    payload = {
        "prompt": prompt,
        "cfg_scale": 0.0,
        "aspect_ratio": "16:9",
        "mode": "base",
        "seed": seed,
        "width": config.IMAGE_WIDTH,
        "height": config.IMAGE_HEIGHT,
    }
    headers = {
        "Authorization": f"Bearer {config.NVIDIA_IMAGE_API_KEY}",
        "Accept": "application/json",
    }

    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(config.NVIDIA_IMAGE_ENDPOINT, headers=headers, json=payload, timeout=180)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"[image_gen] rate-limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            image_url = _extract_image_url(data)
            if not image_url:
                raise RuntimeError(f"no image url in response: {str(data)[:300]}")
            if image_url.startswith("http"):
                img = requests.get(image_url, timeout=180)
                img.raise_for_status()
                with open(out_path, "wb") as f:
                    f.write(img.content)
            else:
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(image_url))
            print(f"[image_gen] saved {out_path} ({os.path.getsize(out_path) // 1024} KB)")
            return out_path
        except Exception as e:
            last_err = e
            print(f"[image_gen] attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))

    raise RuntimeError(f"NVIDIA image gen failed after retries. prompt: {prompt[:80]}... last error: {last_err}")


def _extract_image_url(data: dict) -> str | None:
    """NVIDIA Flux response shape varies — try common fields defensively."""
    if isinstance(data.get("artifacts"), list) and data["artifacts"]:
        a = data["artifacts"][0]
        if isinstance(a, dict):
            return a.get("url") or a.get("base64")
    if "image" in data and isinstance(data["image"], str):
        return data["image"]
    if isinstance(data.get("data"), list) and data["data"]:
        d = data["data"][0]
        if isinstance(d, dict):
            return d.get("url") or d.get("b64_json")
    if "url" in data and isinstance(data["url"], str):
        return data["url"]
    return None


if __name__ == "__main__":
    test_prompt = (
        "Minimalist stick figure illustration, single thin black line on cream off-white background, "
        "no shading, no color, sparse composition, lots of negative space, contemplative mood, flat 2D, "
        "stick figure standing alone on top of a hill at dawn looking out over empty landscape"
    )
    os.makedirs("./output", exist_ok=True)
    generate_image(test_prompt, "./output/test.png", seed=42)
    print("OK")
