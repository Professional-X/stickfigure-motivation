"""Ensure a cinematic music bed exists for the premium pipeline.

The repo ships ./music empty (only .gitkeep). We download a free CC-BY track
from Incompetech (Kevin MacLeod) on first run, cached afterward. Attribution
is required by the CC-BY 4.0 license and is returned here for the description.

If every Incompetech URL is unreachable (rare), we synthesize a soft ambient
pad with ffmpeg so the pipeline never breaks — narration alone still ships.
"""
import os
import requests

from . import scripts  # for nothing — just keeps package import sane

UA = {"User-Agent": (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)}

# Incompetech CC-BY 4.0 cinematic tracks (verified 200 OK 2026-11).
# Each: (filename, display name, mp3 url). Ordered by preference.
TRACKS = [
    ("long_note_two.mp3", "Long Note Two",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Long%20Note%20Two.mp3"),
    ("lightless_dawn.mp3", "Lightless Dawn",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lightless%20Dawn.mp3"),
    ("the_descent.mp3", "The Descent",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Descent.mp3"),
    ("long_note_one.mp3", "Long Note One",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Long%20Note%20One.mp3"),
]


def _verify_audio(url: str) -> bool:
    """Ranged GET of first 4KB to confirm it's real audio (not an error page)."""
    try:
        r = requests.get(url, headers={**UA, "Range": "bytes=0-4095"}, timeout=30, stream=True)
        ctype = r.headers.get("content-type", "")
        return r.status_code in (200, 206) and ("audio" in ctype or "octet-stream" in ctype)
    except Exception:
        return False


def ensure_music(music_dir: str) -> tuple[str, dict]:
    """Return (music_path, attribution_dict).

    Reuses any track already in music_dir. Otherwise downloads the first
    verified Incompetech track. Falls back to a synthesized ambient pad.
    attribution_dict = {track, artist, license, url} or {} if synthesized.
    """
    os.makedirs(music_dir, exist_ok=True)

    # 1. Reuse any existing audio file in music_dir
    for f in sorted(os.listdir(music_dir)):
        if f.lower().endswith((".mp3", ".wav", ".m4a")) and os.path.getsize(os.path.join(music_dir, f)) > 50_000:
            path = os.path.abspath(os.path.join(music_dir, f))
            # Match to known track for attribution, else generic
            attr = _attr_for_file(f)
            print(f"[music] reusing existing: {f}")
            return path, attr

    # 2. Download first verified Incompetech track
    for fname, name, url in TRACKS:
        if not _verify_audio(url):
            print(f"[music] {name}: unavailable, skipping")
            continue
        out_path = os.path.join(music_dir, fname)
        print(f"[music] downloading: {name}")
        try:
            r = requests.get(url, headers=UA, timeout=120, stream=True)
            if r.status_code != 200:
                continue
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    if chunk:
                        fh.write(chunk)
            if os.path.getsize(out_path) > 50_000:
                print(f"[music]   saved {fname} ({os.path.getsize(out_path)//1024} KB)")
                return os.path.abspath(out_path), {
                    "track": name,
                    "artist": "Kevin MacLeod",
                    "license": "CC-BY 4.0",
                    "url": "https://incompetech.com",
                }
        except Exception as e:
            print(f"[music] {name} download failed: {e}")
            continue

    # 3. Fallback: synthesize a soft ambient pad (no attribution needed)
    print("[music] WARNING: no Incompetech track available — synthesizing ambient pad")
    out_path = os.path.join(music_dir, "ambient_pad.wav")
    import subprocess
    # Layered low sines + gentle lowpass -> a calm drone bed
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", "240", "-i",
        "sine=frequency=110:sample_rate=44100",
        "-f", "lavfi", "-t", "240", "-i",
        "sine=frequency=164.81:sample_rate=44100",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2,volume=0.18,lowpass=f=600,afade=t=in:st=0:d=3",
        "-ac", "2", out_path,
    ], check=True, capture_output=True)
    return os.path.abspath(out_path), {}


def _attr_for_file(fname: str) -> dict:
    for tfname, name, _ in TRACKS:
        if fname == tfname:
            return {"track": name, "artist": "Kevin MacLeod",
                    "license": "CC-BY 4.0", "url": "https://incompetech.com"}
    return {}


def attribution_line(attr: dict) -> str:
    """One-line credit for the video description (CC-BY requires this)."""
    if not attr:
        return ""
    return (f"\n\nMusic: \"{attr.get('track','')}\" by {attr.get('artist','')} "
            f"({attr.get('license','')}) — {attr.get('url','')}")
