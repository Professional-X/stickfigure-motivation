"""Premium long-form cinematic pipeline for @StickVerse.

Replaces the stickfigure path when PIPELINE_MODE=premium (the new default).
Reuses the repo's existing tts.py (Edge-TTS), subtitles.py (faster-whisper)
and upload.py (YouTube Data API + Composio fallback) — only the visual layer
is new: real Mixkit footage + Ken Burns + cinematic color grade + burned
subtitles + premium thumbnails.
"""
