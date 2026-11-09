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
) -> str:
    """Upload and return the YouTube video ID (or empty string on skip)."""
    if not os.path.exists(video_path):
        raise RuntimeError(f"video file not found: {video_path}")

    # Path 1: Direct YouTube Data API (recommended)
    if os.environ.get("YOUTUBE_REFRESH_TOKEN") and os.environ.get("YOUTUBE_CLIENT_ID"):
        try:
            return _upload_via_youtube_data_api(video_path, title, description, tags)
        except Exception as e:
            print(f"[upload] YouTube Data API failed: {type(e).__name__}: {e}")
            print("[upload] falling through to Composio...")

    # Path 2: Composio (flaky)
    if config.COMPOSIO_API_KEY and config.COMPOSIO_ENTITY_ID:
        try:
            return _upload_via_composio(video_path, title, description, tags)
        except Exception as e:
            print(f"[upload] Composio failed: {type(e).__name__}: {e}")
            print("[upload] falling through to manual upload...")

    # Path 3: Skip
    print("\n[upload] === AUTOMATIC UPLOAD SKIPPED ===")
    print(f"[upload] video saved locally at: {video_path}")
    print(f"[upload] file size: {os.path.getsize(video_path) / 1024 / 1024:.1f} MB")
    print(f"[upload] The GitHub Actions run also uploads it as an artifact.")
    print(f"[upload] Download from: https://github.com/Professional-X/stickfigure-motivation/actions")
    print(f"[upload] Then upload manually at: https://www.youtube.com/upload")
    print(f"[upload] Title to use: {title[:80]}")
    return ""


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
    video_id = _extract_video_id(data)
    if not video_id:
        # Try nested structures
        if "data" in data:
            video_id = _extract_video_id(data["data"])
        if not video_id:
            print(f"[upload] WARNING: couldn't extract video ID from response")
    return video_id


def _extract_video_id(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("id", "video_id", "videoId", "youtube_video_id"):
            if key in result:
                return str(result[key])
        if "data" in result and isinstance(result["data"], dict):
            for key in ("id", "video_id", "videoId"):
                if key in result["data"]:
                    return str(result["data"][key])
    return str(result)


if __name__ == "__main__":
    print(f"YOUTUBE_REFRESH_TOKEN set: {bool(os.environ.get('YOUTUBE_REFRESH_TOKEN'))}")
    print(f"YOUTUBE_CLIENT_ID set: {bool(os.environ.get('YOUTUBE_CLIENT_ID'))}")
    print(f"COMPOSIO_API_KEY set: {bool(config.COMPOSIO_API_KEY)}")
    print(f"COMPOSIO_ENTITY_ID set: {bool(config.COMPOSIO_ENTITY_ID)}")
