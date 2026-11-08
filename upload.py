"""Upload final video to YouTube via Composio.

Composio wraps the YouTube Data API behind their toolkit — you connect your
Google account once in their dashboard, then call the action with an entity_id.

If Composio's YouTube action isn't set up, this fails cleanly and the pipeline
leaves the video file in place for manual upload.
"""
import os
import config


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
) -> str:
    """Upload and return the YouTube video ID (or Composio response)."""
    if not config.COMPOSIO_API_KEY:
        raise RuntimeError(
            "COMPOSIO_API_KEY not set. Get one at https://composio.dev"
        )
    if not config.COMPOSIO_ENTITY_ID:
        raise RuntimeError(
            "COMPOSIO_ENTITY_ID not set. After connecting your YouTube account "
            "in Composio dashboard, copy the entity_id here."
        )
    if not os.path.exists(video_path):
        raise RuntimeError(f"video file not found: {video_path}")

    # Import lazily so the script can run other steps even if composio isn't installed
    from composio import ComposioToolSet

    toolset = ComposioToolSet(
        api_key=config.COMPOSIO_API_KEY,
        entity_id=config.COMPOSIO_ENTITY_ID,
    )

    # Composio has used several action names over time. Try the most common ones.
    possible_actions = [
        "YOUTUBE_UPLOAD_VIDEO",
        "YOUTUBE_UPLOAD_A_VIDEO",
        "YOUTUBE_VIDEOS_INSERT",
        "YOUTUBE_UPLOAD_VIDEO_ACTION",
    ]

    params = {
        "file_path": os.path.abspath(video_path),
        "title": title[:100],  # YT title limit
        "description": description[:4900],  # YT desc limit
        "tags": tags[:10] if isinstance(tags, list) else tags,
        "category_id": config.YOUTUBE_CATEGORY_ID,
        "privacy_status": config.YOUTUBE_PRIVACY,
    }

    last_err = None
    for action in possible_actions:
        try:
            print(f"[upload] trying Composio action: {action}")
            result = toolset.execute_action(action=action, params=params)
            print(f"[upload] success via {action}")
            return _extract_video_id(result)
        except Exception as e:
            msg = str(e).lower()
            # If the action exists but failed for a real reason, don't try others
            if "not found" not in msg and "no action" not in msg and "unknown action" not in msg:
                # Real failure — surface it
                raise RuntimeError(f"Composio action {action} failed: {e}")
            last_err = e
            continue

    raise RuntimeError(
        f"No matching Composio YouTube upload action found. "
        f"Check your Composio dashboard for the exact action name. "
        f"Last error: {last_err}"
    )


def _extract_video_id(result) -> str:
    """Composio responses come in various shapes — try to find a YT video ID."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("id", "video_id", "videoId", "youtube_video_id"):
            if key in result:
                return str(result[key])
        # nested data
        if "data" in result and isinstance(result["data"], dict):
            for key in ("id", "video_id", "videoId"):
                if key in result["data"]:
                    return str(result["data"][key])
    return str(result)


if __name__ == "__main__":
    # quick check
    print(f"COMPOSIO_API_KEY set: {bool(config.COMPOSIO_API_KEY)}")
    print(f"COMPOSIO_ENTITY_ID set: {bool(config.COMPOSIO_ENTITY_ID)}")
