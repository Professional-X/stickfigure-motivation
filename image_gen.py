"""Generate stick-figure stills via NVIDIA Build Flux.1 dev endpoint.

Docs: https://build.nvidia.com/black-forest-labs/flux-1-dev
The endpoint returns a signed URL (or base64) — we download and save as PNG.
"""
import os
import time
import base64
import requests
import config


def generate_image(prompt: str, out_path: str, seed: int | None = None) -> str:
    """Generate one image and save to out_path. Returns out_path.

    Retries up to 4 times with backoff. NVIDIA build can be flaky under load.
    """
    if seed is None:
        seed = config.IMAGE_SEED

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
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Accept": "application/json",
    }

    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(
                config.IMAGE_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=180,
            )
            if r.status_code == 429:
                # rate-limited — wait longer
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
                # base64-encoded
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(image_url))

            print(f"[image_gen] saved {out_path} ({os.path.getsize(out_path)//1024} KB)")
            return out_path

        except Exception as e:
            last_err = e
            print(f"[image_gen] attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))

    raise RuntimeError(f"image gen failed after retries. prompt: {prompt[:80]}... last error: {last_err}")


def _extract_image_url(data: dict) -> str | None:
    """NVIDIA Flux response shape varies — try common fields defensively."""
    # Shape 1: {"artifacts": [{"url": "..."}]}
    if isinstance(data.get("artifacts"), list) and data["artifacts"]:
        a = data["artifacts"][0]
        if isinstance(a, dict):
            return a.get("url") or a.get("base64")
    # Shape 2: {"image": "..."}
    if "image" in data and isinstance(data["image"], str):
        return data["image"]
    # Shape 3: OpenAI-style {"data": [{"url": "..."}]}
    if isinstance(data.get("data"), list) and data["data"]:
        d = data["data"][0]
        if isinstance(d, dict):
            return d.get("url") or d.get("b64_json")
    # Shape 4: top-level url
    if "url" in data and isinstance(data["url"], str):
        return data["url"]
    return None


if __name__ == "__main__":
    # smoke test
    test_prompt = (
        "Minimalist stick figure illustration, single thin black line on cream off-white background, "
        "no shading, no color, sparse composition, lots of negative space, contemplative mood, flat 2D, "
        "stick figure standing alone on top of a hill at dawn looking out over empty landscape"
    )
    generate_image(test_prompt, "./output/test.png", seed=42)
    print("OK")
