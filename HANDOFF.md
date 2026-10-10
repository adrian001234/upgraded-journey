# HANDOFF - read this first (written 2026-10-10 about 22:30 IST)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, story rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.

## WARNING: other Claude sessions edit this repo in parallel
Between 16:53 and 17:57 IST another session (commits as aliwaziri10) rewrote video/generate_video.py
(Agnes retired agnes-video-v2.0 on 2026-09-25; code now uses agnes-video-2.5-flash, 720P, 4-12 s per shot,
"reference" mode with the character picture) and edited assembly/assemble.py, publish/youtube_upload.py,
tools/reconcile_youtube.py, CLAUDE.md, DEBUGGING_METHODOLOGY.md. Before trusting any note (including this
one) re-read the live file and run list_commits.

## What is running now
- Owner inserted a 4-shot TEST row at ~21:56 IST and started the pipeline by hand at ~22:00 IST
  (it uses the NEW video code).
- Test row: title 'TEST - Nori (4 shots)', status narrated, Episode 1 shots 1, 5, 22, 23
  (EPISODE_01_SHOTS.md), durations [5,4,6,4]. Every shot text contains "Nori the snail" + her full
  description; shot 23 has the first sparrow description. narration_url is null.
- Nobody has seen a render line or a clip yet. The owner has NOT seen any video.

## Next steps (ONE at a time; owner is not technical; every link or value in its own code block
## with a copy button; no tables)
0. First sentence: say which GitHub identity you are connected as (aliwaziri10). Writes returned 403
   earlier; edits go via the GitHub web editor as copy-paste of FULL files. Keep each pasted file under
   about 7000 characters: pastes of 9000+ characters were cut off twice on 2026-10-10. After every
   paste read the live file and check its LAST lines.
1. Owner opens https://github.com/adrian001234/upgraded-journey/actions , newest "Tiny Lawn Tales
   Pipeline" run, step "Video stage", scrolls BELOW the settings block and pastes the lines starting
   "Row ...: rendering shot" (look for "[with character reference image]") and any error. If Agnes says
   503 video_queue_full the code waits 180 s up to 20 times, then leaves the row narrated.
2. Owner runs in https://supabase.com/dashboard/project/dbdtwhzlmzhyidpmeymn/sql/new :
   select id, status, shot_retry_count, retry_count, video_urls from video_pipeline where title like 'TEST%';
   Expected: video_urls fills with 4 links (public bucket video_clips, <row id>/shot_000.mp4 ...), status
   video_complete, then assemble.py FAILS (no narration_url), requeues up to 3 times, then failed. That is
   expected for the test. The owner opens the 4 links to watch the clips.
3. Judge WITH the owner: same snail as the reference picture in all 4 shots? eyes emote? sprinkler water OK?
   sparrow OK? Risk: a shot meant to be WIDE may start close, because the reference picture is a
   side-on medium shot.
4. RENAME the hero to Mimsi. Owner chose it on 2026-10-10 (spelling Mimsi, not Mimsy). The earlier chat
   had chosen Nori, so confirm Mimsi is final. Only AFTER the test job has finished (the running process
   keeps the old name and shot text is re-read from the database each shot) the owner sets repo variable
   CHARACTER_REFERENCE_NAME = Mimsi the snail at
   https://github.com/adrian001234/upgraded-journey/settings/variables/actions . Then in one pass replace
   Nori with Mimsi in the test row shot_list, SHOW_BIBLE.md, EPISODE_01_SHOTS.md, CLAUDE.md.
   The picture file stays refs/pip.png.
5. Do NOT render all 40 shots until the test is judged. Then: fixed descriptions for the sparrow, the
   mossy log with the round door, the sprinkler and the crumb in SHOW_BIBLE.md; write 40 full shot
   prompts; insert Episode 1 as status narrated.

## Facts read live on 2026-10-10 (re-verify)
- video_pipeline columns: id uuid, title, source, link, script, video_url, status (all text),
  created_at/updated_at/published_at, youtube_video_id, youtube_url, shot_list jsonb, narration,
  narration_url text, shot_durations jsonb, video_urls jsonb, retry_count int, shot_retry_count int.
  Unused extras (leave alone): video_next_index, setting_and_characters, has_recurring_person,
  character_reference_url, music_mood, music_generated, sfx_applied_count, total_shots,
  shots_completed, narration_full, generation_status.
- Rows at ~21:52 IST: 1 old news row (failed), 0 rows narrated/video_complete/video_generated. It had
  20+ rows at 15:00 IST; who deleted them is unknown.
- Assembly is still the OLD news version: needs narration_url, mixes it with a quiet ambient bed.
  Needs a rewrite for music + sound effects.
- Publish: header says Tiny Lawn Tales, but it still uploads PUBLIC, categoryId 28 (Science and
  Technology), has no made-for-kids flag, and takes the description from the script column. Gated by
  repo variable YOUTUBE_READY (owner says false). Review before it is ever true, and confirm which
  YouTube channel YT_REFRESH_TOKEN belongs to first.
- Supabase project was paused until 13:57 IST on 2026-10-10 (caused "Name or service not known").
  Banner says grace period is over - it may pause again.
- Hero picture: https://dbdtwhzlmzhyidpmeymn.supabase.co/storage/v1/object/public/video_clips/refs/pip.png
  (not re-opened since; re-verify the letters).

## Decisions
- Channel Tiny Lawn Tales. Hero = girl garden snail, orange shell with cream swirl, big eyes on stalks.
  Dropped names: Pebble (pillbug), Pip, Pippa (sounds like Peppa), Nori (working name in repo).
  Mimsi: shallow search found no collision; owner has not searched YouTube.
- Episodes about 3 minutes (Episode 1 = 40 shots, about 172 s). Owner wants 10-15 minute videos =
  bundle 4-5 episodes into compilations.
- The owner has NOT approved the story. He wants to see video first.

## Not verified
Any render, any clip, Agnes credits and limits, per-shot render time, whether the picture URL loads,
YOUTUBE_READY value, YouTube search for "Tiny Lawn Tales" and "Mimsi snail".

## To do after the test
Sound (free music + effects, rewrite assemble.py); update publish for kids; owner renames the YouTube
channel and checks the token's channel; only then YOUTUBE_READY=true; episodes 2-5 and compilations.
