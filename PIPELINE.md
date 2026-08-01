# TechPulse — AI Video Pipeline

Niche: Tech / AI / Science news briefs (short, punchy, "here's what just changed" style)

## Pipeline Stages (single GitHub Actions workflow, all stages run as steps)

1. **Research** — `research/` — daily trending tech/AI/science topic sourcing
2. **Script** — `script/generate_script.py` — FreeLLMAPI/Gemini generates the news-brief
   script + scene list (`script/latest_scripts.json`), flags `has_recurring_person`
3. **Video** — `video/generate_video.py` — Agnes AI (agnes-video-v2.0) generates one
   clip per scene. For has_recurring_person=true stories, uses image-to-video
   continuity anchoring (character reference on scene 0, then last-frame-of-previous-
   scene on every scene after) - same architecture as the Marius pipeline.
4. **Narration** — `narration/generate_narration.py` — Edge TTS narration track
5. **Assembly** — `assembly/assemble.py` — muxes video + narration into final mp4
6. **Tracking** — `tracking/save_to_supabase.py` — uploads final video to Supabase
   Storage `videos` bucket, inserts real-status row into `video_pipeline` table
   (status=video_generated only on a real successful upload, else status=failed)
7. **Publish** — pushes finished video to the TechPulse channel (stub until channel is live)
8. **Analytics** — post-publish performance tracking (added after first videos are live)

## Status
- Channel: TechPulse — pending YouTube ID verification (~24hr)
- Pipeline runs end-to-end: script → video → narration → assembly → Supabase sync all working.

## Fix Log

### 2026-08-02 — Continuity anchor upload switched from tmpfiles.org to Supabase Storage
**Problem:** `video/generate_video.py`'s `upload_to_tmpfiles()` was hosting the
per-scene continuity-anchor frame on tmpfiles.org (free, anonymous, no key). A full
workflow run showed `tmpfiles upload failed... HTTP Error 403: Forbidden` on all
7/7 anchor upload attempts - tmpfiles.org rejected every request from the GitHub
Actions runner. Effect: every scene after scene 0 fell back to the *original*
character reference image instead of chaining from the previous scene's actual
last frame - clips still generated (7/7), but true per-scene continuity was
silently degraded every run since this was wired up.

**Root cause:** third-party free host with no reliability guarantee, unlike Marius's
pipeline which uploads continuity anchors directly to its own Supabase Storage bucket.

**Fix:** replaced `upload_to_tmpfiles()` with `upload_to_supabase()` in
`video/generate_video.py` - uploads the extracted frame to this project's own
Supabase Storage instead of a third-party host, using the existing
`SUPABASE_URL`/`SUPABASE_ANON_KEY` secrets already present in this repo (same
credentials `tracking/save_to_supabase.py` uses).

**Supabase changes (project `dbdtwhzlmzhyidpmeymn`):**
- Created new bucket `video_clips` (public), didn't exist before.
- Added RLS policies on `storage.objects` for `video_clips`: anon insert, anon
  update (upsert), anon+authenticated select - mirrors the existing `videos`
  bucket policy pattern.

**Verification status:** code change + bucket/RLS change both live. Not yet
confirmed against a real workflow run - next run's logs should show
`Supabase anchor upload failed` disappear and scene-to-scene continuity anchors
actually rotating (not stuck on one static reference image) - re-verify against
live logs, don't trust this doc at face value.
