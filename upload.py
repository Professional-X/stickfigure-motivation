"""Upload final video to YouTube.

Strategy (in priority order):
1. YouTube Data API v3 (direct) — if YOUTUBE_REFRESH_TOKEN env var is set
   Most reliable. Requires one-time OAuth setup (see README).
2. Composio YouTube v3.1 API — if COMPOSIO_API_KEY + COMPOSIO_ENTITY_ID are set
   Uses the correct v3.1 flow: file upload to S3 → execute YOUTUBE_MULTIPART_UPLOAD_VIDEO.
3. Skip upload — print clear instructions for manual upload from artifact.

The pipeline never fails just because upload failed. The video is always
saved as a GitHub Actions artifact for manual download.
"""
import os
import json
import time
import requests
import config


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: str | None = None,
) -> str:
    """Upload and return the YouTube video ID (or empty string on skip).

    If thumbnail_path is given and upload succeeds, the custom thumbnail is
    set on the video via the YouTube Data API thumbnails.set endpoint
    (direct API only — Composio does not expose thumbnail upload).
    """
    if not os.path.exists(video_path):
        raise RuntimeError(f"video file not found: {video_path}")

    video_id = ""

    # Path 1: Direct YouTube Data API (recommended)
    if os.environ.get("YOUTUBE_REFRESH_TOKEN") and os.environ.get("YOUTUBE_CLIENT_ID"):
        try:
            video_id = _upload_via_youtube_data_api(video_path, title, description, tags)
        except Exception as e:
            print(f"[upload] YouTube Data API failed: {type(e).__name__}: {e}")
            print("[upload] falling through to Composio...")

    # Path 2: Composio (flaky)
    if not video_id and config.COMPOSIO_API_KEY and config.COMPOSIO_ENTITY_ID:
        try:
            video_id = _upload_via_composio(video_path, title, description, tags)
        except Exception as e:
            print(f"[upload] Composio failed: {type(e).__name__}: {e}")
            print("[upload] falling through to manual upload...")

    # Path 3: Skip
    if not video_id:
        print("\n[upload] === AUTOMATIC UPLOAD SKIPPED ===")
        print(f"[upload] video saved locally at: {video_path}")
        print(f"[upload] file size: {os.path.getsize(video_path) / 1024 / 1024:.1f} MB")
        print(f"[upload] The GitHub Actions run also uploads it as an artifact.")
        print(f"[upload] Download from: https://github.com/Professional-X/stickfigure-motivation/actions")
        print(f"[upload] Then upload manually at: https://www.youtube.com/upload")
        print(f"[upload] Title to use: {title[:80]}")
        return ""

    # Upload succeeded — now set the custom thumbnail (direct API only)
    if thumbnail_path and os.path.exists(thumbnail_path):
        _set_thumbnail(video_id, thumbnail_path)

    return video_id


def _set_thumbnail(video_id: str, thumbnail_path: str) -> bool:
    """Set a custom thumbnail on an uploaded video via YouTube Data API.

    Requires the same OAuth refresh token as the upload. Custom thumbnails
    need the YouTube account verified (https://www.youtube.com/verify) — if
    the account isn't verified, this returns 400 and we warn but don't fail
    the whole upload (the video is already up).
    """
    if not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        print("[upload] thumbnail: skipped (no YouTube OAuth refresh token)")
        return False
    if not os.path.exists(thumbnail_path):
        print(f"[upload] thumbnail: file not found ({thumbnail_path})")
        return False

    print(f"[upload] setting custom thumbnail: {os.path.basename(thumbnail_path)}")
    try:
        client_id = os.environ["YOUTUBE_CLIENT_ID"]
        client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
        refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

        # refresh access token
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        r.raise_for_status()
        access_token = r.json()["access_token"]

        # POST the image to the thumbnails.set endpoint
        with open(thumbnail_path, "rb") as f:
            img_bytes = f.read()
        r = requests.post(
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "image/png",
            },
            data=img_bytes,
            timeout=120,
        )
        if r.status_code in (200, 201):
            print(f"[upload] thumbnail set successfully on video {video_id}")
            return True
        # Common failure: account not verified for custom thumbnails
        print(f"[upload] thumbnail set failed: HTTP {r.status_code} {r.text[:300]}")
        if r.status_code == 400 and "verify" in r.text.lower():
            print("[upload] NOTE: custom thumbnails require a verified YouTube account.")
            print("[upload]       Verify at https://www.youtube.com/verify (takes ~24h).")
        return False
    except Exception as e:
        print(f"[upload] thumbnail set exception: {type(e).__name__}: {e}")
        return False


def _upload_via_youtube_data_api(video_path, title, description, tags) -> str:
    """Direct YouTube Data API v3 upload using OAuth refresh token.

    Setup (one-time):
    1. Go to https://console.cloud.google.com/
    2. Create a project, enable YouTube Data API v3
    3. Create OAuth 2.0 Client ID (Desktop app type)
    4. Run `python get_youtube_oauth.py` (in this repo) to obtain a refresh token
    5. Set env vars: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
    """
    import urllib.parse
    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

    # Step 1: Exchange refresh token for access token
    print("[upload] refreshing YouTube OAuth token...")
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    access_token = r.json()["access_token"]

    # Step 2: Resumable upload — initiate session
    print(f"[upload] initiating resumable upload for: {title[:60]}")
    file_size = os.path.getsize(video_path)
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:10] if isinstance(tags, list) else [],
            "categoryId": config.YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": config.YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        },
        json=metadata,
        timeout=60,
    )
    r.raise_for_status()
    upload_url = r.headers.get("Location")
    if not upload_url:
        raise RuntimeError("no upload URL returned by YouTube")

    # Step 3: Upload the video bytes
    print(f"[upload] uploading {file_size / 1024 / 1024:.1f} MB to YouTube...")
    with open(video_path, "rb") as f:
        r = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
            },
            data=f,
            timeout=600,
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed: HTTP {r.status_code} {r.text[:300]}")

    video_id = r.json().get("id", "")
    print(f"[upload] === uploaded: https://youtube.com/watch?v={video_id} ===")
    return video_id


def _upload_via_composio(video_path, title, description, tags) -> str:
    """Composio YouTube upload via v3.1 API.

    Composio deprecated v1 (returns 410). The correct v3.1 flow is:
      1. POST /api/v3.1/files/upload/request → get presigned S3 URL + s3key
      2. PUT video bytes to the presigned URL
      3. POST /api/v3.1/tools/execute/YOUTUBE_MULTIPART_UPLOAD_VIDEO
         with videoFile = {name, mimetype, s3key}

    All requests use x-api-key header (not Authorization Bearer).
    Base URL is backend.composio.dev (NOT api.composio.dev — that hostname
    doesn't resolve in DNS).
    """
    import hashlib

    COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1"
    headers = {"x-api-key": config.COMPOSIO_API_KEY, "Content-Type": "application/json"}

    # Step 1: Read file, compute MD5
    print(f"[upload] reading video file: {video_path}")
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    file_size = len(video_bytes)
    md5 = hashlib.md5(video_bytes).hexdigest()
    print(f"[upload] file size: {file_size} bytes, md5: {md5}")

    # Step 2: Request presigned upload URL
    print("[upload] requesting presigned S3 URL from Composio...")
    r = requests.post(
        f"{COMPOSIO_BASE}/files/upload/request",
        headers=headers,
        json={
            "toolkit_slug": "youtube",
            "tool_slug": "YOUTUBE_MULTIPART_UPLOAD_VIDEO",
            "filename": os.path.basename(video_path),
            "mimetype": "video/mp4",
            "md5": md5,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Composio file upload request failed: HTTP {r.status_code} {r.text[:500]}")

    upload_data = r.json()
    s3key = upload_data["key"]
    presigned_url = upload_data["new_presigned_url"]
    print(f"[upload] got presigned URL, s3key: {s3key[:80]}...")

    # Step 3: Upload to S3 via presigned URL (PUT request, raw bytes)
    print(f"[upload] uploading {file_size} bytes to Composio's S3...")
    r = requests.put(
        presigned_url,
        data=video_bytes,
        headers={"Content-Type": "video/mp4"},
        timeout=600,
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"S3 upload failed: HTTP {r.status_code} {r.text[:500]}")
    print("[upload] S3 upload complete")

    # Step 4: Execute the YouTube upload tool
    print("[upload] executing YOUTUBE_MULTIPART_UPLOAD_VIDEO...")
    payload = {
        "entity_id": config.COMPOSIO_ENTITY_ID,
        "arguments": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:10] if isinstance(tags, list) else [],
            "categoryId": config.YOUTUBE_CATEGORY_ID,
            "privacyStatus": config.YOUTUBE_PRIVACY,
            "videoFile": {
                "name": os.path.basename(video_path),
                "mimetype": "video/mp4",
                "s3key": s3key,
            },
        },
    }
    r = requests.post(
        f"{COMPOSIO_BASE}/tools/execute/YOUTUBE_MULTIPART_UPLOAD_VIDEO",
        headers=headers,
        json=payload,
        timeout=600,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(
            f"YouTube upload execution failed: HTTP {r.status_code} {r.text[:500]}"
        )

    data = r.json()
    print(f"[upload] Composio response: {json.dumps(data, indent=2)[:500]}")

    # CRITICAL: Composio returns HTTP 200 even when the underlying YouTube call
    # failed (e.g. 429 quota exceeded). The error is nested inside data.data.
    # Check for http_error / error fields before extracting the video ID.
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    if isinstance(inner, dict):
        # Look for any error indicators
        http_err = inner.get("http_error") or inner.get("error")
        err_msg = inner.get("message") or inner.get("error_message")
        if http_err or (err_msg and "error" in str(err_msg).lower()[:50]):
            raise RuntimeError(
                f"YouTube API call failed: {http_err or err_msg}"
            )

    video_id = _extract_video_id(data)
    if not video_id:
        # Try nested structures
        if "data" in data:
            video_id = _extract_video_id(data["data"])
        if not video_id:
            print(f"[upload] WARNING: couldn't extract video ID from response")
    return video_id


def _extract_video_id(result) -> str:
    """Extract a YouTube video ID from a Composio response.

    Composio nests the YouTube response in various shapes depending on version:
      {"data": {"id": "abc123"}}
      {"data": {"video": {"id": "abc123"}}}
      {"data": {"successful": [...], "data": {"id": "abc123"}}}
    Recursively search all nested dicts for the first key matching
    id/video_id/videoId/youtube_video_id whose value looks like a YouTube ID
    (11-char string). Falls back to str(result) if nothing found.
    """
    def _looks_like_yt_id(val) -> bool:
        return isinstance(val, str) and len(val) == 11 and val.isalnum()

    def _search(obj):
        if isinstance(obj, str):
            if _looks_like_yt_id(obj):
                return obj
            return None
        if isinstance(obj, dict):
            # check direct keys first (prefer id over video_id)
            for key in ("id", "video_id", "videoId", "youtube_video_id"):
                if key in obj and _looks_like_yt_id(obj[key]):
                    return obj[key]
            # then recurse into nested dicts/lists
            for v in obj.values():
                found = _search(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _search(item)
                if found:
                    return found
        return None

    found = _search(result)
    if found:
        return found
    # last resort: if result is a plain string, return it as-is
    if isinstance(result, str):
        return result
    print(f"[upload] WARNING: couldn't extract video ID from response shape: {str(result)[:200]}")
    return ""


if __name__ == "__main__":
    print(f"YOUTUBE_REFRESH_TOKEN set: {bool(os.environ.get('YOUTUBE_REFRESH_TOKEN'))}")
    print(f"YOUTUBE_CLIENT_ID set: {bool(os.environ.get('YOUTUBE_CLIENT_ID'))}")
    print(f"COMPOSIO_API_KEY set: {bool(config.COMPOSIO_API_KEY)}")
    print(f"COMPOSIO_ENTITY_ID set: {bool(config.COMPOSIO_ENTITY_ID)}")
