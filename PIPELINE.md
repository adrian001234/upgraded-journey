# Tiny Lawn Tales Pipeline - Status

Last verified live against GitHub + Supabase: 2026-10-10 about 22:05 IST (see "What is NOT verified").
Re-verify against live data before trusting this doc at face value - it drifts.
Show rules, the hero and the story plan live in SHOW_BIBLE.md.
Episode 1 shot list (draft) is in EPISODE_01_SHOTS.md. Working rules are in CLAUDE.md.

## NEXT PROFILE START HERE (written 2026-10-10 about 22:05 IST)
A 4-shot TEST of Episode 1 was inserted and the pipeline was started by hand. The owner
has NOT seen any video yet. Goal now: see the test clips, judge them WITH the owner, then
rename the hero, then decide: render all 40 shots or rework.

Do these in order, ONE step at a time with the owner (not technical; every link, value or
file goes in its own code block with a copy button, never in a table):
0. First sentence: say which GitHub identity you are connected as (aliwaziri10). Writes to
   this repo returned 403 per an earlier session (not retested since) - all edits go
   through the GitHub web editor as copy-paste, full files only, then verify live.
1. Ask the owner to open https://github.com/adrian001234/upgraded-journey/actions , click
   the newest "Tiny Lawn Tales Pipeline" run, open the "Video stage" step, scroll BELOW the
   settings block and paste the lines that start with "Row ...: rendering shot". Look for
   "[with character reference image]" on each shot. The owner pasted only the settings
   block before; the render lines were never seen.
2. Ask the owner to run in https://supabase.com/dashboard/project/dbdtwhzlmzhyidpmeymn/sql/new :
     select id, status, shot_retry_count, retry_count, video_urls from video_pipeline where title like 'TEST%';
   Expected: status goes narrated -> video_complete (video_urls has 4 clip links) -> then
   assembly FAILS because narration_url is null (expected for the test; assemble.py
   requeues to video_complete up to 3 times, then sets failed - the clips stay in
   video_urls). Clips are in the PUBLIC bucket video_clips under <row id>/shot_000.mp4 etc.,
   so the owner can open each link in a browser.
3. Judge the clips with the owner: does the snail look like the reference picture in all 4
   shots (orange shell with cream swirl, big eyes on stalks)? Do her eyes emote? Does the
   sprinkler water look acceptable? Does the sparrow look OK? Known risk: with
   image-to-video, EVERY shot with her name starts from her reference picture (a
   side-on medium-ish shot), so shots that are meant to be WIDE may start close.
4. RENAME the hero (owner decision, see Decisions): after the test job has finished, the
   owner changes repo variable CHARACTER_REFERENCE_NAME to  Mimsi the snail  at
   https://github.com/adrian001234/upgraded-journey/settings/variables/actions (pencil icon).
   Do NOT change it while the job is running: the video stage re-reads each shot's text from
   the database but the running process keeps the old name from its start, so the picture
   would stop being attached. Right after, in one pass: update the shot text in the test
   row (replace Nori with Mimsi), SHOW_BIBLE.md, EPISODE_01_SHOTS.md and this file.
   The reference picture file stays refs/pip.png (only its file name is old).
5. Only after the test is judged: add fixed descriptions for the sparrow, the mossy log with
   the tiny round door, the sprinkler and the crumb to SHOW_BIBLE.md, then write all 40 shots
   as full prompts and insert Episode 1. Do not render all 40 before the test is judged.

## Live database facts (read by the assistant on 2026-10-10, re-verify)
- video_pipeline columns (types): id uuid, title text, source text, link text, script text,
  video_url text, status text, created_at/updated_at/published_at timestamptz,
  youtube_video_id text, youtube_url text, shot_list jsonb, narration text,
  narration_url text, shot_durations jsonb, video_urls jsonb, video_next_index integer,
  setting_and_characters text, has_recurring_person boolean, character_reference_url text,
  music_mood text, music_generated boolean, sfx_applied_count integer, total_shots integer,
  shots_completed integer, narration_full text, generation_status text, retry_count integer,
  shot_retry_count integer.
  The columns from video_next_index to generation_status are NOT used by the current
  video/assembly/publish code - leave them alone.
- At ~15:00 IST the table had 20+ rows: 19 old news rows status failed, 1 scripted
  (2 Sept). At ~21:51 IST it had exactly 1 row (failed) and 0 rows with status in
  (narrated, video_complete, video_generated). Cause of the disappearance unknown (the
  owner may have cleaned it). Re-check before inserting anything else.
- Test row inserted ~21:56 IST: title 'TEST - Nori (4 shots)', source 'tiny-lawn-tales',
  status 'narrated', shot_list = Episode 1 shots 1, 5, 22, 23 (each visual_description
  contains the exact words "Nori the snail" + her full description; shot 23 also has the
  first sparrow description: small plump brown house sparrow, streaked brown and tan
  feathers, grey cheeks, black bib, short cone-shaped beak, one big round shiny black eye),
  shot_durations [5,4,6,4], video_urls [], retry_count 0, shot_retry_count 0, narration_url null.
- The pipeline was started manually (Run workflow) at ~22:00 IST. At 22:01 the owner pasted
  the start of the Video stage log (settings only, no render lines). Reference variable
  showed CHARACTER_REFERENCE_URL ending /storage/v1/object/public/video_clips/refs/pip.png and
  CHARACTER_REFERENCE_NAME = Nori the snail.

## What changed on 2026-10-10 (commit SHAs, all by owner
