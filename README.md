# Stick Figure Motivation — Fully Automated YouTube Channel

A GitHub Actions cron job that produces and uploads a 15-20 minute stick-figure motivation video three times a week. No manual work after the initial setup.

## What it does

Every Mon / Wed / Fri at 09:00 UTC, the workflow:

1. **Picks a theme** from `themes.py` (discipline / stoicism / loneliness / anti-modern life)
2. **Writes a ~3,000-word script** via NVIDIA Build LLM (default: Llama 3.3 70B)
3. **Breaks the script into 35 scenes** with per-scene image prompts
4. **Generates 35 stick-figure illustrations** via NVIDIA Build Flux.1 dev (free)
5. **Narrates each scene** with Edge-TTS (deep male voice, free)
6. **Transcribes narration with Whisper** (faster-whisper on CPU, free)
7. **Burns in karaoke-style subtitles** (word-by-word highlight)
8. **Composes the final video** with ffmpeg: Ken Burns zoom on each image + background music + subtitles
9. **Uploads to YouTube** via Composio
10. **Keeps the artifact** for 7 days in case you want to inspect or re-upload

**Total cost per video: $0.00** (all on NVIDIA Build free tier + free TTS + free Whisper + free GitHub Actions minutes)

---

## Setup — 30 minutes

### 1. Get the NVIDIA Build API key

1. Go to https://build.nvidia.com
2. Sign in with any account
3. Browse to any model (e.g. `meta/llama-3.3-70b-instruct`)
4. Click "Get API Key" in the top right
5. Copy the key — it starts with `nvapi-`

### 2. Set up Composio + YouTube

1. Go to https://composio.dev and sign up
2. From the dashboard, add the **YouTube** integration
3. Follow the OAuth flow to connect the Google account that owns your YouTube channel
4. Copy:
   - Your **API key**
   - The **entity_id** of the connected YouTube account (shown in the Composio dashboard under "Connected Accounts")

> Note: Composio's free tier covers ~1000 actions/month, which is plenty for 3 uploads/week.

### 3. Create the GitHub repo

1. Create a new private repo on GitHub (e.g. `stickfigure-motivation`)
2. Unzip this project and push it:
   ```bash
   git init
   git add .
   git commit -m "initial commit"
   git branch -M main
   git remote add origin https://github.com/<YOU>/<REPO>.git
   git push -u origin main
   ```

### 4. Push secrets to GitHub via the setup script (recommended)

Instead of pasting secrets into the GitHub UI one by one, use the included `setup_secrets.py`:

```bash
# 1. Create .env from the template and fill in your real values
cp .env.example .env
# Edit .env — set GH_PAT, NVIDIA_API_KEY, COMPOSIO_API_KEY, COMPOSIO_ENTITY_ID

# 2. Install deps
pip install -r requirements.txt

# 3. Run the setup (replace owner/repo with YOUR repo)
python setup_secrets.py yourname/stickfigure-motivation
```

The script encrypts each secret with libsodium and pushes it to your repo via the GitHub API, then verifies they're stored.

### 4-alt. Add GitHub Secrets manually

If you prefer the web UI: in your repo go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `NVIDIA_API_KEY` | your `nvapi-...` key |
| `COMPOSIO_API_KEY` | your Composio API key |
| `COMPOSIO_ENTITY_ID` | your YouTube Connected Account ID (starts with `ca_`) |

### 5. (Optional) Add background music

Drop royalty-free MP3 files into `./music/`. The pipeline picks one randomly per video. Good sources:

- https://pixabay.com/music/ (search "ambient", "piano", "melancholic")
- YouTube Audio Library
- Free Music Archive

If `./music/` is empty, the video still generates — just without background music.

### 6. Test it manually first

In your repo: **Actions → "Publish Stick Figure Motivation" → Run workflow**

The first run takes ~40-60 minutes (mostly Whisper transcription + ffmpeg encoding). Watch the logs.

### 7. ROTATE ALL EXPOSED KEYS (mandatory if any key was pasted in chat)

If you shared any API key or PAT in a chat, screenshot, or commit message — even once — it is compromised. Rotate immediately:

- **GitHub PAT**: https://github.com/settings/tokens → delete old, create new with `repo` + `workflow` scopes
- **Composio API key**: https://app.composio.dev/api-keys → revoke old, generate new → update the `COMPOSIO_API_KEY` GitHub Secret
- **NVIDIA API key**: https://build.nvidia.com → account settings → regenerate → update the `NVIDIA_API_KEY` GitHub Secret

The Composio Connected Account ID (`ca_...`) is not secret — it's safe to keep.

---

## Configuration

Edit `config.py` to change anything:

```python
LLM_MODEL = "meta/llama-3.3-70b-instruct"     # swap to mistralai/mistral-large-2-instruct
                                               # or qwen/qwen2.5-72b-instruct

TTS_VOICE = "en-US-GuyNeural"                  # deep male (default)
                                               # alternates: en-US-AndrewNeural (warmer),
                                               #             en-US-DavisNeural (rough)

SCENES_PER_VIDEO = 35                          # ~30 sec per scene = ~17-18 min total
BG_MUSIC_VOLUME_DB = -22                       # quieter = more negative
YOUTUBE_PRIVACY = "public"                     # public | unlisted | private
```

To switch LLM per-run without editing code: add a GitHub **Variable** (not Secret) named `LLM_MODEL` in Settings → Secrets and variables → Actions → Variables.

---

## Customizing themes

Edit `themes.py`. The bank has 4 categories (discipline, stoicism, loneliness, anti_modern), each with 7+ themes. The pipeline picks one deterministically per day (seeded by date) so videos don't repeat. Add more themes to expand the rotation.

The more specific the theme, the better — generic prompts like "be disciplined" produce generic scripts. Specific angles like "Marcus Aurelius was the most powerful man on earth. He still wrote reminders to stay humble" produce sharper videos.

---

## File structure

```
.
├── .github/workflows/publish.yml   # the cron job
├── config.py                       # all knobs (model, voice, scenes, etc.)
├── themes.py                       # rotating theme bank
├── script_gen.py                   # NVIDIA LLM: theme -> script -> scenes
├── image_gen.py                    # NVIDIA Flux.1 dev: prompt -> PNG
├── tts.py                          # Edge-TTS: text -> MP3 + duration
├── subtitles.py                    # faster-whisper: audio -> ASS karaoke
├── compose.py                      # ffmpeg: images + audio + subs -> MP4
├── upload.py                       # Composio: MP4 -> YouTube
├── pipeline.py                     # orchestrator (entry point)
├── music/                          # you drop royalty-free MP3s here
├── output/                         # generated videos (gitignored)
├── requirements.txt
└── .env.example
```

---

## Running locally

```bash
# 1. Install ffmpeg (macOS: brew install ffmpeg, Linux: apt install ffmpeg)
# 2. Clone, set up venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Copy env file and fill in keys
cp .env.example .env
# edit .env with your NVIDIA_API_KEY, COMPOSIO_API_KEY, COMPOSIO_ENTITY_ID

# 4. Run
python pipeline.py
```

Output lands in `./output/<timestamp>/final.mp4`.

---

## Troubleshooting

**"no image url in response"** — NVIDIA build endpoint shape changed. Check `image_gen.py:_extract_image_url` and add the new field. Print the raw response to debug.

**Composio upload action not found** — Composio occasionally renames actions. Open Composio dashboard → YouTube integration → note the exact action name → add it to `possible_actions` list in `upload.py`.

**Whisper too slow on GitHub Actions** — Already using `base.en` + CPU + int8. If still slow, switch to `tiny.en` (lower accuracy, 2x faster) in `subtitles.py`.

**Video too long / too short** — Adjust `SCENES_PER_VIDEO` in `config.py`. 35 scenes × ~30 sec = ~17 min. 40 scenes ≈ 20 min.

**Stylistic issues with scripts** — Edit `SYSTEM_PROMPT` and `SCRIPT_PROMPT` in `script_gen.py`. The banned words list is the main quality lever.

**Subtitles look bad** — Edit `to_ass()` in `subtitles.py`. Change `font_name`, `font_size`, chunk size, or colors. The ASS format docs: https://trac.ffmpeg.org/wiki/HowToBurnSubtitlesIntoVideo

---

## Cost breakdown (all free)

| Component | Cost |
|---|---|
| NVIDIA Build LLM (Llama 3.3 70B) | Free tier (1,000 calls/month) |
| NVIDIA Build Flux.1 dev | Free tier (1,000 calls/month) |
| Edge-TTS | Free |
| faster-whisper | Free (runs locally on CPU) |
| Composio | Free tier (1,000 actions/month) |
| GitHub Actions | 2,000 free minutes/month for private repos |
| YouTube upload | Free |
| **Per video** | **$0.00** |

You can run 3 videos/week (~13/month) comfortably inside all free tiers.

---

## Why this works as a channel

The "stick figure + deep male voice + stoic script" format is genuinely popular right now. Channels like **Improvement Pill**, **The Painted Turtle**, and several anonymous "discipline" channels have proven the format. The aesthetic — minimalist line drawings on cream backgrounds — signals "contemplative, serious, not commercial" which is exactly the audience this niche attracts (men 18-35, late at night, scrolling for motivation).

The automation lets you publish consistently without burning out, which is the single biggest factor in YouTube channel growth. The first 30-50 videos will get few views; that's normal. The algorithm needs consistency to identify your audience.

---

## Security notes

- **Never commit `.env`** — it's in `.gitignore` for a reason.
- **Never hardcode API keys in code** — always use env vars / GitHub Secrets.
- **Rotate any key you accidentally expose** — if you paste a key in a chat, screenshot, or commit, regenerate it immediately at the source.
- The `output/` directory is gitignored. The Action uploads it as an artifact for 7 days so you can debug without committing large video files.
