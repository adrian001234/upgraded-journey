# Tiny Lawn Tales Pipeline - Status

Last verified live against GitHub + Supabase: 2026-10-10.
Re-verify against live data before trusting this doc at face value - it drifts.
Show rules, the hero (Nori the snail) and the story plan live in SHOW_BIBLE.md.

## History
The repo used to be the TechPulse news channel. On 2026-10-10 the news stages
(research, script, narration), the old tracking script, the auto-fixer and the
credit reminder bot were deleted. The pipeline is now a wordless 3D comedy channel.

## Architecture (single workflow, Supabase-native)

One GitHub Actions workflow (.github/workflows/pipeline.yml, named "Tiny Lawn Tales
Pipeline"), cron every 5 minutes, concurrency group tiny-lawn-tales-pipeline with
cancel-in-progress false so overlapping triggers queue instead of racing.
timeout-minutes 300.

Every episode is a single video_pipeline row in Supabase, updated in place by every
stage. Nothing downstream matches rows by title or text.

Episodes are NOT created by a script stage any more. A row is inserted by hand
(with Claude's help) already at status 'narrated'.

Status progression: narrated -> video_complete -> video_generated -> published
(or failed after RETRY_LIMIT, where retry logic exists).

| Stage | File | Reads | Writes | Notes |
|---|---|---|---|---|
| Video | video/generate_video.py | oldest status='narrated' row (shot_list + shot_durations) | video_urls, status='video_complete' | Agnes API, one shot at a time, paced 65s (1 request/minute cap). If vars CHARACTER_REFERENCE_URL and CHARACTER_REFERENCE_NAME are set, any shot whose text contains the name ("Nori the snail") starts from her reference picture. |
| Assembly | assembly/assemble.py | oldest status='video_complete' row | video_url, status='video_generated' | ffmpeg concat plus audio. Still the OLD news version: it requires narration_url and mixes it with a quiet ambient bed. Needs a rewrite for music and sound effects. |
| Publish | publish/youtube_upload.py | oldest status='video_generated' row with youtube_video_id null | youtube_video_id, youtube_url, published_at, status='published' | Gated behind repo variable YOUTUBE_READY. Currently set to false on purpose. Not yet reviewed or updated for the new channel (title, description, tags, thumbnail, made-for-kids). |

Other workflows: make_character_sheet.yml (manual button, makes the character
reference picture), reconcile_youtube.yml (manual, checks YouTube against Supabase).

## Repo settings the pipeline depends on
- Secrets: AGNES_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, YT_CLIENT_ID,
  YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- Variables: CHARACTER_REFERENCE_URL, CHARACTER_REFERENCE_NAME ("Nori the snail"),
  YOUTUBE_READY (false until the channel is ready)

## Still to do (in order)
1. Write the full 40-shot list for Episode 1 and insert it as a 'narrated' row.
2. Sound: music plus sound effects (free sources only). Rewrite assembly for it.
3. Update publish for the new channel; confirm which YouTube channel the refresh
   token is authorized for BEFORE any upload; set "made for kids" correctly.
4. Rename the YouTube channel to Tiny Lawn Tales in YouTube Studio.
5. Only then set YOUTUBE_READY back to true.

## Known-good fixes already live (don't re-break these)
- Video, Assembly and Publish agree on shot_list / visual_description /
  shot_durations / video_urls. Verify the neighbours before editing any one stage.
- timeout-minutes 300: up to 45 sequential Agnes shots can run in one job.
- Assembly and Publish match by row id and retry via retry_count before permanent
  failed. Don't reintroduce text-based matching.
- Agnes content-policy rejection fails the row immediately. Reword that shot in
  shot_list and reset the row to 'narrated' to resume.

## Standing risks
- Supabase free projects can be paused. On 2026-10-10 the project was paused, which
  made SUPABASE_URL stop resolving ("Name or service not known" in the logs) and
  looked like a wrong secret. Fix: restore the project from the Supabase dashboard.
- public.video_shots table: RLS disabled and no longer used. Candidate for dropping.
- Agnes: 1 request/minute for this account. 40 shots take 45+ minutes. Real renders
  can take 14-38 minutes under load.
- The public video_clips bucket keeps every clip. Cleanup after publish is not built.

## GitHub write access
Writes by Claude to this repo return 403 (retested 2026-10-10). All edits go through
the GitHub web editor: Claude gives the exact
https://github.com/adrian001234/upgraded-journey/edit/main/<path> link and the full
file, the owner pastes and commits, then Claude re-verifies live.
