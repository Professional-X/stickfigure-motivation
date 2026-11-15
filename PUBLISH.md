# Publishing @StickVerse Premium Videos

This repo now generates **premium long-form cinematic motivation videos** and
uploads them to YouTube automatically. The stickfigure pipeline is kept as a
fallback (`pipeline.py`) but the scheduled/manual workflow runs the premium
path (`pipeline_premium.py`).

---

## One-click publish (the only step that needs you)

The YouTube upload can only run on the **GitHub Actions runner**, because the
OAuth credentials (`YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` /
`YOUTUBE_REFRESH_TOKEN`) and the Composio fallback key live in the repo's
**GitHub Secrets** — they are not available anywhere else, by design. So
publishing is a one-click trigger after you push the code:

1. **Commit + push** the premium pipeline to your GitHub repo:
   ```bash
   git add premium/ pipeline_premium.py .github/workflows/publish.yml requirements.txt PUBLISH.md
   git commit -m "feat: premium long-form cinematic pipeline (Mixkit + Ken Burns + grade)"
   git push origin main
   ```
2. **Trigger the workflow** (publishes video 1 immediately):
   - Go to your repo → **Actions** tab → **"Publish StickVerse Premium"**.
   - Click **"Run workflow"** (the `workflow_dispatch` trigger) → branch `main`.
   - The run takes ~10–15 min: it generates the video, uploads it, and commits
     `output/<run_id>/metadata.json` + `thumbnail.png` + `uploaded.txt`.
3. **After it's published**, the YouTube link is in
   `output/<run_id>/uploaded.txt` (also printed in the Actions log).

After that, it runs **automatically twice a week** — Wed + Sat at 17:00 UTC
(9am Pacific / 12pm Eastern / 5pm London) — publishing the next unpublished
topic each time.

### Why I couldn't push the button for you

I built and validated the entire pipeline in my sandbox and even produced
video 1 there (see `download/`), but the sandbox has **no `gh` CLI, no git
remote, and no YouTube/Composio credentials** — so I can't push to your repo
or call the YouTube API from here. The commit + the one-click trigger are the
only steps that must happen on your side.

---

## What the workflow does, end to end (fully free — $0/video)

| Stage | Tool | Cost |
|---|---|---|
| Script | Curated in `premium/scripts.py` (no LLM) | $0 |
| Narration | Edge-TTS `en-US-GuyNeural` (free) | $0 |
| Subtitles | faster-whisper `base.en` (local, CPU) | $0 |
| Footage | Mixkit free stock (commercial use, no attribution) | $0 |
| Music | Incompetech CC-BY 4.0 (Kevin MacLeod, attribution in description) | $0 |
| Compose | ffmpeg (Ken Burns + teal-orange grade + vignette + ducked music) | $0 |
| Thumbnail | Pillow (clip still + bold title + handle, 3 variants) | $0 |
| Upload | YouTube Data API (direct OAuth) + Composio fallback | $0 |

No `OPENROUTER_API_KEY` is needed for the premium path (scripts are curated).
The upload secrets are the only credentials required, and they're already
configured from the previous stickfigure runs.

---

## Topic queue (video 1 publishes first)

`premium/scripts.py` defines the rotation. The queue
(`premium/queue.pick_topic`) picks the first topic whose `topic_id` is not yet
in `output/*/uploaded.txt`, so they publish in order:

1. **Stop Asking For An Easier Life** (Stoicism) ← publishes first
2. You Are Not Behind (Mindset)
3. The Cost Of Who You Almost Became (Discipline)
4. Discipline Is Remembering What You Want (Discipline)

After #4, it loops back to #1. Add more topics by appending to `TOPICS` in
`premium/scripts.py` (same dict shape: `id`, `category`, `title`, `scenes`,
`description`, `tags`, `hashtags`, `thumbnail_text`).

Each video is **~3:10–3:20** (6 scenes, ~550 words) — long but tightly paced;
every scene (hook → problem → shift → core → application → resolution) earns
its place.

---

## Verifying a run

In the Actions run page:
- **"Generate and publish premium video"** step prints the topic, per-scene
  durations, and the final YouTube link:
  `=== uploaded: https://youtube.com/watch?v=<id> ===`
- The **"video-output-<run_id>" artifact** contains the full workspace
  (`final.mp4`, `thumbnail.png`, `subtitles.ass`, `clips/`, `stills/`).
- `output/<run_id>/uploaded.txt` (committed) confirms the upload landed.
- If both upload paths fail, the run writes
  `output/<run_id>/MANUAL_UPLOAD_NEEDED.txt` — re-trigger the workflow the
  next day, or upload manually (see below). There is no automatic retry system
  (it was buggy and has been removed).

## Manual upload fallback

If both upload paths fail, the run writes
`output/<run_id>/MANUAL_UPLOAD_NEEDED.txt` with the title, description, tags,
and thumbnail path. Download `final.mp4` + `thumbnail.png` from the run
artifact and upload at https://www.youtube.com/upload.

---

## Files added / changed

**New — `premium/` module:**
- `premium/scripts.py` — curated long-form scripts (video 1 + 3 rotation topics)
- `premium/queue.py` — picks next unpublished topic
- `premium/mixkit.py` — Mixkit scraper + downloader (free stock, no attribution)
- `premium/music.py` — Incompetech CC-BY music fetcher + attribution
- `premium/compose.py` — cinematic composer (Ken Burns + grade + ducked music)
- `premium/thumbnails.py` — 3 cinematic thumbnail variants
- `premium/subtitles.py` — 1920×1080 ASS (reuses whisper transcribe)
- `premium/metadata.py` — SEO title/description/tags

**New orchestrator:** `pipeline_premium.py` (reuses existing `tts.py`,
`subtitles.py`, `upload.py`).

**Changed:** `.github/workflows/publish.yml` (runs `pipeline_premium.py`,
caches whisper model + music), `requirements.txt` (+`beautifulsoup4`, `lxml`).

**Unchanged:** `upload.py`, `get_youtube_oauth.py` — reused as-is.

**Removed:** `retry_upload.py` + `.github/workflows/retry_upload.yml` (the
buggy hourly retry system) — deleted. The workflow runs once per trigger; if
the upload fails, just re-trigger it manually from the Actions tab.
