# TechPulse — AI Video Pipeline

Niche: Tech / AI / Science news briefs, published as **long-form** videos
(16:9, 3-5+ min target — upgraded from the original short-form/Shorts format;
current live videos are still ~30s landscape as the long-form script rework
is in progress).

## Pipeline Stages (single GitHub Actions workflow `pipeline.yml`, runs every 15 min via cron)

1. **Gate** — checks Supabase for any row in `scripted/narrated/video_complete`
   status; only starts a new story if none in progress.
2. **Research** — `research/sources.py`
3. **Script** — `script/generate_script.py` — Gemini generates script + scene
   list, `[SFX: ...]` / `[VOICE:quote]` tags for engagement audio.
4. **Narration** — `narration/generate_narration.py` — Chatterbox-TTS (local)
   + faster-whisper for caption timing; strips SFX/VOICE tags, aligns them to
   word timestamps.
5. **Video** — `video/generate_video.py` — Agnes AI (agnes-video-v2.0), one
   clip per scene, image-to-video continuity anchoring for recurring-person
   stories (anchor frames uploaded to Supabase Storage, not tmpfiles.org —
   fixed 2026-08-02).
6. **Assembly** — `assembly/assemble.py` — muxes video + narration into final
   mp4. No burned-in captions (removed 2026-08-03 — YouTube auto-CC handles
   it; SRT is generated but not yet used as a real caption track upload).
7. **Publish** — `publish/youtube_upload.py` — gated by repo variable
   `YOUTUBE_READY` (currently `true`). Pulls the oldest `video_generated` row
   with no `youtube_video_id`, uploads to YouTube, writes back `status=published`
   + `youtube_video_id`/`youtube_url` on that same row by `id`.

There is no separate "Tracking" stage — each stage writes its own status to
the `video_pipeline` table directly via Supabase REST.

## Known-fixed issues (see repo commit history / auto-heal commits for detail)
- **2026-08-04**: schema mismatch across script/video/narration stages from
  uncoordinated single-file patches (some manual, one from `autoheal/heal.py`).
- **2026-08-04**: `publish/youtube_upload.py` used to match rows back together
  by title+source text after upload, which could silently drop the link
  between a completed YouTube upload and its Supabase row. Rewritten to match
  by the row's own stable `id` — no text matching involved anymore.
- **2026-08-05**: `public.video_pipeline` had RLS policies for `INSERT` and
  `SELECT` only — no `UPDATE` policy for `anon`. Every status write-back
  (`mark_published`, `mark_failed`, and other stages' PATCH calls) was being
  silently rejected. This is why 11 videos were live on YouTube while Supabase
  still showed them as `video_generated`, and why the pipeline got stuck
  retrying the oldest unresolved row instead of moving to new stories. Fixed
  by adding an `anon` `UPDATE` policy. Backlog manually reconciled same day.
  If future PATCH calls silently stop persisting again, check RLS policies
  first before assuming it's a code bug.
- **2026-08-05**: dropped unused `public.video_shots` table — RLS was
  disabled on it (public read/write via anon key) and no current code
  referenced it.

## Standing open items
- 3 old rows (from 2026-07-23 / 2026-07-31) never successfully uploaded to
  YouTube at all — unresolved as of 2026-08-05, `video_url` may be stale.
- `autoheal/heal.py` (triggered by `.github/workflows/auto_heal.yml`) can
  auto-patch and commit to `main` on pipeline failure, with no cross-file
  schema awareness. Not yet disabled/constrained — pending a decision.
- Long-form script rework (more scenes/narration, multi-headline videos) not
  yet built — current videos are still short-form length despite the
  long-form decision.

**Verify against live commit history / Supabase state before trusting this
file at face value on anything time-sensitive — update it whenever a real
fix lands, don't let it drift again.**
