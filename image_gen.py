"""Generate stick-figure stills via HuggingFace Inference API (free Flux.1-dev).

Docs: https://huggingface.co/docs/api-inference
The endpoint returns image bytes directly (image/png) when ready, or HTTP 503
while the model loads — we retry with backoff in that case.

Legacy NVIDIA Build support kept as a fallback path (use IMAGE_PROVIDER=nvidia
to switch back, but you need the "Public API Endpoints" entitlement enabled).
"""
import os
import time
import requests
import config


def generate_image(prompt: str, out_path: str, seed: int | None = None) -> str:
    """Generate one image and save to out_path. Returns out_path.

    Routes to the configured provider (default: HuggingFace).
    """
    if config.IMAGE_PROVIDER == "nvidia":
        return _generate_nvidia(prompt, out_path, seed)
    return _generate_huggingface(prompt, out_path, seed)


def _generate_huggingface(prompt: str, out_path: str, seed: int | None = None) -> str:
    """Generate via HuggingFace Inference API. Free, ~5-30s per image.

    The free tier has these characteristics:
    - First request after idle: HTTP 503 + ~20-40s warmup
    - Subsequent requests: 5-15s each
    - Heavy rate-limiting if you hammer it — we sleep 1s between calls in
      pipeline.py to stay safe
    """
    if not config.HF_API_TOKEN:
        raise RuntimeError("HF_API_TOKEN not set. Get one at https://huggingface.co/settings/tokens")

    headers = {
        "Authorization": f"Bearer {config.HF_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "image/png",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "width": config.IMAGE_WIDTH,
            "height": config.IMAGE_HEIGHT,
            "seed": seed if seed is not None else config.IMAGE_SEED,
            "num_inference_steps": 28,  # Flux default; lower = faster, lower quality
            "guidance_scale": 3.5,
        },
    }

    last_err = None
    for attempt in range(5):
        try:
            r = requests.post(
                config.HF_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=180,
            )

            if r.status_code == 200:
                ctype = r.headers.get("content-type", "")
                if "image" not in ctype:
                    # Sometimes HF returns JSON error even with 200
                    last_err = f"unexpected content-type: {ctype}, body: {r.text[:300]}"
                    print(f"[image_gen] {last_err}")
                    time.sleep(8)
                    continue
                with open(out_path, "wb") as f:
                    f.write(r.content)
                print(f"[image_gen] saved {out_path} ({len(r.content) // 1024} KB)")
                return out_path

            if r.status_code == 503:
                # Model loading — HF tells us estimated time
                wait = 15
                try:
                    data = r.json()
                    if "estimated_time" in data:
                        wait = min(int(data["estimated_time"]) + 3, 60)
                except Exception:
                    pass
                print(f"[image_gen] model loading (503), waiting {wait}s... (attempt {attempt + 1})")
                time.sleep(wait)
                continue

            if r.status_code == 429:
                # Rate limit — back off hard
                wait = 30 * (attempt + 1)
                print(f"[image_gen] rate-limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue

            # Any other error
            last_err = f"HTTP {r.status_code}: {r.text[:300]}"
            print(f"[image_gen] {last_err}")
            time.sleep(8)

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[image_gen] attempt {attempt + 1} exception: {last_err}")
            time.sleep(8)

    raise RuntimeError(
        f"HuggingFace image gen failed after retries. prompt: {prompt[:80]}... last error: {last_err}"
    )


def _generate_nvidia(prompt: str, out_path: str, seed: int | None = None) -> str:
    """Legacy NVIDIA Build Flux endpoint. Kept for reference — most accounts
    don't have the 'Public API Endpoints' entitlement enabled.
    """
    import base64
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
        "Authorization": f"Bearer {config.NVIDIA_IMAGE_API_KEY}",
        "Accept": "application/json",
    }

    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(
                config.NVIDIA_IMAGE_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=180,
            )
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
