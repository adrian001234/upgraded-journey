# TechPulse — AI Video Pipeline

Niche: Tech / AI / Science news briefs. Currently **short-form** (~30s
landscape). Long-form rework (matching Erased/Alternate Earth quality bar)
is a pending decision, not yet built — target length not yet chosen between
full 5-7+ min (needs full resumable shot-by-shot checkpointing) or a shorter
2-3 min middle ground.

## Pipeline Stages
Single GitHub Actions workflow `pipeline.yml` ("TechPulse Pipeline"), runs
every 15 min via cron (also supports manual `workflow_dispatch` from the
Actions tab). Gates: only starts a new story if no row is in
`scripted`/`narrated`/`video_complete`.

1. **Research** — `research/sources.py`
2. **Script** — `script/generate_script.py` — Gemini generates script + scene
   list, `[SFX: ...]` / `[VOICE:quote]` tags for engagement audio.
3. **Narration** — `narration/generate_narration.py` — Chatterbox-TTS (local)
   + faster-whisper for caption timing; strips SFX/VOICE tags, aligns them to
   word timestamps. Voice reference: Mark F. Smith (LibriVox), see
   "Narrator voice" section below.
4. **Video** — `video/generate_video.py` — Agnes AI (agnes-video-v2.0), one
   clip per scene, image-to-video continuity anchoring for recurring-person
   stories (anchor frames in Supabase Storage). Has retry logic for failed
   video processing (added 2026-08-04).
5. **Assembly** — `assembly/assemble.py` — muxes video + narration into final
   mp4. No burned-in captions (YouTube auto-CC handles it; SRT is generated
   but not used as a real caption track upload). Has retry logic for failed
   processing (added 2026-08-04, same change as the video stage).
6. **Publish** — `publish/youtube_upload.py` — gated by repo variable
   `YOUTUBE_READY` (currently `true`). Pulls the oldest `video_generated` row
   with no `youtube_video_id`, uploads to YouTube, writes back
   `status=published` + `youtube_video_id`/`youtube_url` on that same row by
   its stable `id` (not by title/source text matching).

There is no separate "Tracking" stage — each stage writes its own status to
the `video_pipeline` table directly via Supabase REST, matched by row `id`
throughout.

## Narrator voice (Chatterbox reference clip) — added 2026-08-06

- Voice: **Mark F. Smith**, LibriVox narrator (`https://librivox.org/reader/204`),
  reference clip pulled from his reading of "The Call of the Wild"
  (archive.org item `call_ofthe_wild_1010_librivox`, VBR 128kbps mp3 — the
  64kbps version was too muffled/noisy after denoising, don't reuse it).
- Reference clip: 15s trimmed/denoised sample, stored in a public Supabase
  Storage bucket `voice-reference`, file `mark_smith_vbr_sample (1).wav`.
  Its public URL is set as the `CHATTERBOX_VOICE_REF_URL` repo variable
  (GitHub → Settings → Secrets and variables → Actions → Variables).
- `generate_narration.py` downloads this URL once per run and passes it to
  Chatterbox as `audio_prompt_path`, with `EXAGGERATION=0.4` /
  `CFG_WEIGHT=0.4` (tuned for a steadier, less theatrical documentary read
  than Chatterbox's 0.5/0.5 defaults).
- Same commit also fixed two audio-quality bugs: sentence-stitch clicks
  (fixed with a 12ms fade in/out on every sentence clip before
  concatenation) and an atempo warble on the 0.92x slowdown pass (fixed by
  upsampling to 48kHz before the tempo change and back down after, instead
  of applying it directly at 24kHz).
- **`pipeline.yml`'s narration step needs `CHATTERBOX_VOICE_REF_URL` in its
  own `env:` block** — repo variables are NOT automatically available to a
  step's script, they must be explicitly wired as
  `${{ vars.CHATTERBOX_VOICE_REF_URL }}`. This was missed on the first pass
  and would have caused a `KeyError` — already fixed, but if this variable
  is ever renamed, remember to update `pipeline.yml` too, not just the repo
  variable itself.
- **STATUS: code is live on main, but as of end of session 2026-08-06 the
  actual voice output has NOT been confirmed on a real pipeline run.** A
  manual test row was inserted directly into `video_pipeline`
  (`status='scripted'`, short 2-sentence script) specifically to force a
  narration-stage run without waiting on the existing backlog — check that
  row first in the next session (see Standing open items below).

## Known-fixed issues (do not re-diagnose these)
- `video_pipeline` had RLS `INSERT`/`SELECT` policies but no `UPDATE` policy
  for `anon` — every status write-back (mark_published, mark_failed, other
  PATCH calls) was silently rejected. This caused videos to go live on
  YouTube while Supabase still showed an earlier status, and caused the
  pipeline to get stuck retrying the oldest unresolved row instead of moving
  on. Fixed 2026-08-05 by adding an `anon` UPDATE policy; backlog manually
  reconciled same day. **If PATCH writes silently stop persisting again,
  check RLS policies first before assuming it's a code bug.**
- Dropped unused `public.video_shots` table (RLS was disabled/open, no
  current code referenced it).
- Publish stage used to match rows back together by title+source text after
  upload, which could silently drop the link between a completed YouTube
  upload and its Supabase row. Rewritten to match by the row's own stable
  `id` — no text matching involved anymore.

## Auto-heal — redesigned 2026-08-06, safe to leave enabled
`autoheal/heal.py` (triggered by `.github/workflows/auto_heal.yml`) runs
when the main pipeline fails, diagnoses the traceback, and drafts a fix via
Gemini. It used to commit that fix straight to `main` with no human
checkpoint — that's the exact mechanism behind the 2026-08-04/05
schema-mismatch incident (see git history), so it's been redesigned:
- **Never commits to `main`.** Opens a PR on a new branch instead
  (`auto-heal/<file>`) — a human must review and merge before the fix takes
  effect.
- Won't open a duplicate PR if one's already open for the same file.
- No longer auto-retriggers the pipeline after proposing a fix — the
  existing 15-min cron already covers that, so healthy stories keep
  moving/publishing on schedule regardless of an open auto-heal PR.
- Any fix touching `publish/` (the YouTube upload code) gets an explicit
  "⚠️ HIGH RISK" prefix on the PR title, since a bad fix there has the
  highest real-world consequence (duplicate uploads, wrong-channel uploads).
- Still scoped to only `research/`, `script/`, `video/`, `narration/`,
  `assembly/`, `tracking/`, `publish/` — never touches workflow files or
  itself. Still skips non-code failures (quota/auth/timeout/outage) rather
  than inventing a fix for something no code patch can solve.

## Standing open items
- **Confirm the new narrator voice actually works on a real pipeline run**
  (see "Narrator voice" section above) — check test row id
  `1a6375b7-be9d-440a-854f-941a84835c43` first. Delete that row from
  `video_pipeline` once confirmed working (it's test data, not a real
  story) — don't delete before confirming, in case a retry is needed.
- 3 old rows (2026-07-23 / 2026-07-31) never successfully uploaded to
  YouTube at all — unresolved, `video_url` may be stale.
- Long-form rework (more scenes/narration, multi-headline videos) not yet
  built — current videos are still short-form length.

**Verify against live commit history / Supabase state before trusting this
file at face value on anything time-sensitive — update it whenever a real
fix lands, don't let it drift again.**
