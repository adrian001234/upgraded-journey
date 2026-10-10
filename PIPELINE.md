# Tiny Lawn Tales Pipeline - Status

Last verified live against GitHub + Supabase: 2026-10-10 (see section "What is NOT verified").
Re-verify against live data before trusting this doc at face value - it drifts.
Show rules, the hero (Nori the snail) and the story plan live in SHOW_BIBLE.md.
Episode 1 shot list (draft) is in EPISODE_01_SHOTS.md. Working rules are in CLAUDE.md.

## NEXT PROFILE START HERE (written 2026-10-10, about 15:00 IST)
Task: render a 4-shot TEST of Episode 1 BEFORE committing to all 40 shots.
Why: the owner has not seen any video yet and cannot judge the story on paper.

Do these in order, ONE step at a time with the owner (he is not technical; every
link/value/file goes in its own code block):
0. First sentence: say which GitHub identity you are connected as (aliwaziri10).
   Writes to this repo return 403 per a previous session (not retested by the session
   that wrote this) - everything goes through the GitHub web editor as copy-paste.
1. DANGER CHECK. The Supabase project was paused ~a month and was restored on
   2026-10-10 around 13:57 IST. The old news pipeline may have created news rows in
   that window, and the video stage renders ANY row with status 'narrated' (spends
   Agnes credits). Ask the owner to run in the Supabase SQL editor
   (https://supabase.com/dashboard/project/dbdtwhzlmzhyidpmeymn/sql/new):
     select id, title, status, created_at from video_pipeline order by created_at desc limit 20;
   Any old news row with status narrated / video_complete / video_generated must be set
   to 'failed' (or deleted) before the test row is inserted.
2. Get the live column types (the owner ran this once but the output never reached the
   assistant): 
     select column_name, data_type from information_schema.columns where table_name = 'video_pipeline' order by ordinal_position;
   Needed to know whether shot_list / shot_durations / video_urls are jsonb or arrays.
3. Write ONE copy-paste SQL block that inserts a test row: title 'TEST - Nori',
   status 'narrated', shot_list = shots 1, 5, 22, 23 of EPISODE_01_SHOTS.md, shot_durations
   = [5, 4, 6, 4]. Each visual_description must start with the exact words
   "Nori the snail" plus her full description from SHOW_BIBLE.md (the video code
   attaches her reference picture only when that phrase is in the shot text). The sparrow
   shot (23) needs a full sparrow description too (none exists yet - write one).
   Set narration_url NULL for the test.
4. The cron picks the row up within 5 minutes (Actions tab). Expected: video stage
   renders the 4 shots (65s apart, renders may take 14-38 min each), row becomes
   video_complete, then assembly FAILS because narration_url is empty. That is expected
   for the test. The clip links are in video_urls - show the owner the clips.
5. Judge with the owner: does Nori look the same in every clip, do her eyes emote, do
   the sprinkler water and the sparrow look acceptable? Then decide: full 40 shots or
   rework. Do not render all 40 before this test is judged.

## What changed on 2026-10-10 (commit SHAs, all by owner pasting via the web editor)
- Reference-image support in video stage: 2cc027f (video/generate_video.py)
- Character sheet helper + button: 4c93f05, 922e5b8 (make_character_sheet.py / .yml)
- Character prompt edits: 81a931a (pillbug, orange dot), 4810cc0 (final: Nori the snail)
- pipeline.yml rewritten (news stages removed, character vars passed): 32c2b1c
- Deleted news code: fe5add9 (research), 4c334ab (script), 016ab68 (narration),
  798464e + 55594ca (auto-fixer), db253ee (tracking/save_to_supabase.py),
  e1f324b + 3a16692 (credit reminder bot)
- Docs: c8288a9 (README), 32decdc (SHOW_BIBLE.md), d9281ad (CLAUDE.md),
  804feab (this file, previous version), 24f96c7 (EPISODE_01_SHOTS.md)

## Decisions made (owner has not yet approved the story)
- Channel: Tiny Lawn Tales. Hero: Nori the snail (girl). Earlier names dropped: Pebble
  the pillbug (face too expressionless, 6 legs glitch in AI video), Pip (used in kids
  media: Pip and Posy, Pip Ahoy!), Pippa (sounds like Peppa Pig).
- Format: episodes about 3 minutes each (Episode 1 draft = 40 shots, about 172 s).
  The owner wants 10-15 minute videos: plan is to publish each episode on its own and
  bundle 4-5 into 12-15 minute compilations (Larva and Oggy do the same). Not a single
  12-minute story.
- Owner approved NOTHING on the story yet - he asked to see a video first. The test in
  "NEXT PROFILE START HERE" is that.

## Confirmed live (read by the assistant from GitHub on 2026-10-10)
- pipeline.yml, make_character_sheet.py, generate_video.py, README.md, SHOW_BIBLE.md,
  CLAUDE.md, EPISODE_01_SHOTS.md all match what was given.
- Repo has no research/, script/, narration/, autoheal/, scripts/ folders;
  workflows left: make_character_sheet.yml, pipeline.yml, reconcile_youtube.yml.
- Supabase project upgraded-journey: owner screenshot showed status Healthy after
  Restore (about 13:57 IST). Project URL read from that screenshot:
  https://dbdtwhzlmzhyidpmeymn.supabase.co  (re-verify the letters).
- Make Character Sheet workflow went green and printed the uploaded path
  refs/pip.png in bucket video_clips (owner also showed the Nori picture).

## What is NOT verified (re-check before acting)
- That the Nori picture URL loads in a browser:
  https://dbdtwhzlmzhyidpmeymn.supabase.co/storage/v1/object/public/video_clips/refs/pip.png
  (file is called pip.png only because that was her first name; keep that name)
- Owner REPORTED (not checked by the assistant) that these repo variables are saved:
  YOUTUBE_READY = false, CHARACTER_REFERENCE_URL = the link above,
  CHARACTER_REFERENCE_NAME = Nori the snail.
- What is currently in video_pipeline (see DANGER CHECK) and its real column types.
- That Agnes accepts image-to-video from this picture, and that it renders 5-6 second
  clips. Real speed per shot is unknown (notes say 14-38 min under load).
- Agnes credit limit unknown. Rule: free tools only until the business makes $5,000.
- Owner has not yet searched YouTube for "Nori snail" to see if a big channel exists.
- The Supabase banner says "Grace period is over" (free-plan quota notice). The project
  paused once already; it may pause again.

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
| Publish | publish/youtube_upload.py | oldest status='video_generated' row with youtube_video_id null | youtube_video_id, youtube_url, published_at, status='published' | Gated behind repo variable YOUTUBE_READY. Must stay false until the channel is ready. Not yet reviewed or updated for the new channel (title, description, tags, thumbnail, made-for-kids). |

Other workflows: make_character_sheet.yml (manual button, makes the character
reference picture), reconcile_youtube.yml (manual, checks YouTube against Supabase).
Other files kept: tools/reconcile_youtube.py, tracking/setup.sql (original table
definition only - the live table has more columns added later), DEBUGGING_METHODOLOGY.md.

## Repo settings the pipeline depends on
- Secrets: AGNES_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, YT_CLIENT_ID,
  YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- Variables: CHARACTER_REFERENCE_URL, CHARACTER_REFERENCE_NAME ("Nori the snail"),
  YOUTUBE_READY (false until the channel is ready)

## Still to do (in order, after the test)
1. Add full fixed descriptions for the sparrow, mossy log with tiny round door,
   sprinkler and crumb to SHOW_BIBLE.md (only Nori has one so far).
2. Write all 40 shots as full video prompts and insert Episode 1 as a 'narrated' row.
3. Sound: music plus sound effects (free sources only). Rewrite assembly for it.
4. Update publish for the new channel; confirm which YouTube channel the refresh
   token is authorized for BEFORE any upload; set "made for kids" correctly.
5. Owner renames the YouTube channel to Tiny Lawn Tales in YouTube Studio.
6. Only then set YOUTUBE_READY back to true.
7. Episodes 2-5, then 12-15 minute compilations.

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
- Leftover rows from the old news show can be rendered by the video stage and spend
  credits (see DANGER CHECK).
- public.video_shots table: RLS disabled and no longer used. Candidate for dropping.
- Agnes: 1 request/minute for this account. 40 shots take 45+ minutes minimum.
- Using one reference picture as the start of every Nori shot may make clips begin in
  the same pose. If so, use it only for close and medium shots.
- The public video_clips bucket keeps every clip. Cleanup after publish is not built.

## GitHub write access
Writes by Claude to this repo returned 403 according to a previous session (this
session did not retest). All edits go through the GitHub web editor: Claude gives the
exact https://github.com/adrian001234/upgraded-journey/edit/main/<path> link and the
full file, the owner pastes and commits, then Claude re-verifies live.
