# TechPulse — AI Video Pipeline

Niche: Tech / AI / Science news briefs. Currently **short-form** (~30s
landscape). Long-form rework (matching Erased/Alternate Earth quality bar)
is a pending decision, not yet built — target length not yet chosen between
full 5-7+ min (needs full resumable shot-by-shot checkpointing) or a shorter
2-3 min middle ground.

## Pipeline Stages
Single GitHub Actions workflow `pipeline.yml`, runs every 15 min via cron.
Gates: only starts a new story if no row is in `scripted`/`narrated`/`video_complete`.

1. **Research** — `research/sources.py`
2. **Script** — `script/generate_script.py` — Gemini generates script + scene
   list, `[SFX: ...]` / `[VOICE:quote]` tags for engagement audio.
3. **Narration** — `narration/generate_narration.py` — Chatterbox-TTS (local)
   + faster-whisper for caption timing; strips SFX/VOICE tags, aligns them to
   word timestamps.
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

## Standing open items
- 3 old rows (2026-07-23 / 2026-07-31) never successfully uploaded to
  YouTube at all — unresolved, `video_url` may be stale.
- `autoheal/heal.py` (triggered by `.github/workflows/auto_heal.yml`) can
  auto-patch and commit to `main` on pipeline failure, with no cross-file
  schema awareness. Not yet disabled/constrained — pending a decision.
- Long-form rework (more scenes/narration, multi-headline videos) not yet
  built — current videos are still short-form length.

**Verify against live commit history / Supabase state before trusting this
file at face value on anything time-sensitive — update it whenever a real
fix lands, don't let it drift again.**
