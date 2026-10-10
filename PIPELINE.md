# Tiny Lawn Tales Pipeline - architecture (stable facts only)
What is happening now and the next steps: see HANDOFF.md.
Written 2026-10-10, updated 2026-10-11. Other sessions edit this repo, so re-read the live files before relying on this.

## How it runs
One workflow, .github/workflows/pipeline.yml ("Tiny Lawn Tales Pipeline"): cron every 5 minutes, plus
the manual "Run workflow" button. Overlapping runs queue (concurrency group tiny-lawn-tales-pipeline).
Timeout 300 minutes.

Each episode is ONE row in the Supabase table video_pipeline, updated in place by every stage.
Episodes are inserted by hand, already at status narrated. There is no script or narration stage any
more (the old news stages were deleted on 2026-10-10).
Status flow: narrated -> video_complete -> video_generated -> published (failed after retries).

## Stages
- Video, video/generate_video.py: takes the oldest narrated row and renders it shot by shot with Agnes
  (agnes-video-2.5-flash, 1 request per minute). A shot whose text contains the character name is
  rendered from her reference picture. Saves progress after every shot. Sets video_complete.
- Assembly, assembly/assemble.py: takes the oldest video_complete row, joins the clips with ffmpeg and
  adds audio. Still the old news version (needs narration_url). Sets video_generated.
- Publish, publish/youtube_upload.py: takes the oldest video_generated row and uploads it to YouTube.
  Runs only when the repo variable YOUTUBE_READY is true.

Other workflows: make_character_sheet.yml (manual button, makes the reference picture) and
reconcile_youtube.yml (manual, checks YouTube against the database).

## Repo settings
- Secrets: AGNES_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- Variables: CHARACTER_REFERENCE_URL, CHARACTER_REFERENCE_NAME, YOUTUBE_READY (keep false until the
  channel is ready)

## Rules that keep it working
- Video, assembly and publish must agree on shot_list, visual_description, shot_durations, video_urls
  and the status values. Read the neighbouring stage before editing one.
- Assembly and publish match rows by id and retry through retry_count.
- A content-policy rejection fails the row: reword that shot and set the status back to narrated.
- Agnes allows 1 request per minute. A render can take 14-38 minutes under load.
- When Agnes answers 503 video_queue_full, the video stage waits 3 minutes and tries again, up to 20
  times in one run. If the queue is still full it stops and leaves the row narrated WITHOUT using up a
  retry; the next scheduled run tries again. Other errors use the normal retries (3 per shot).
- At the start of every run, saved clip links are checked. A dead link means that clip is thrown away
  and rendered again.

## Known risks
- Free Supabase projects pause. A paused project makes SUPABASE_URL fail with "Name or service not known".
- Old rows with status narrated get rendered and spend credits. Check the table before inserting.
- The video_clips bucket keeps every clip; cleanup is not built. Never empty that whole bucket: the
  character pictures live in its refs folder.
