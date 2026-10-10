# HANDOFF - read this first (updated 2026-10-10 night)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.
Other Claude sessions edit this repo in parallel: re-read live files and run list_commits before trusting any note.

## Owner rules
- Not technical. ONE step at a time, plain words, every link/value in its own code block, no tables.
- Be proactive. Say first which GitHub identity you are connected to (get_me). Writes from the connector return 403,
  so edits go through the GitHub web editor as copy-paste of FULL files under ~7000 characters. After every paste,
  read the live file and check its LAST lines. Never upload a file named like one that exists: the browser renames it
  to "NAME (1).md" (this happened to HANDOFF.md). Paste into the edit page instead.
- Owner asked for honest disagreement, not agreement.

## State right now
- YouTube channel renamed to Tiny Lawn Tales, description published (owner said). Old TechPulse videos being set
  to Private (in progress, not verified). YOUTUBE_READY must stay false (publish only runs when it is exactly true).
- Hero: Mimsi the snail, spelled M-I-M-S-I (Mimsy is something else online). Rival: the sparrow. Model: two main
  characters, other ground critters visit in single episodes, friends later (ideas: speedy ladybug, baby snail).
- Reference picture RENAMED to refs/mimsi.png (was pip.png). Repo variable CHARACTER_REFERENCE_URL was updated by
  the owner to .../storage/v1/object/public/video_clips/refs/mimsi.png and CHARACTER_REFERENCE_NAME = Mimsi the snail
  (screenshot confirmed the name; URL value was pasted by the owner before the rename). The owner has not yet said
  whether the picture opens and looks like Mimsi.
- Supabase project dbdtwhzlmzhyidpmeymn is connected to Claude (list_projects, execute_sql work).
- The ONE row in video_pipeline: 'TEST - Mimsi (4 shots)', status narrated, 0 clips, 0 retries, untouched since
  16:26 UTC (checked 20:08 UTC). NOTHING HAS RENDERED YET. No real Agnes clip exists.
- Code checked by a sandbox mock test (pretend Agnes + database): all 4 shots rendered, Mimsi shots used
  reference mode, sparrow shot text-only, ended video_complete. Not yet proven against real Agnes.
- pipeline.yml is correct (cron every 5 min, Video then Assembly then Publish only if YOUTUBE_READY == 'true').

## Next steps (one at a time)
1. Owner opens https://github.com/adrian001234/upgraded-journey/actions/workflows/pipeline.yml . If a run is
   spinning, open it; else click Run workflow. Then run-pipeline -> Video stage. Ask which step is spinning/green/red
   and for the lines starting "Row ...". Likely silent causes: Agnes 503 video_queue_full (code waits quietly up to
   60 min and writes nothing to the database), a slow first shot (up to 15 min), or scheduled runs not happening.
2. When clips exist, owner opens them (public bucket video_clips, <row id>/shot_000.mp4 ...). Judge together: same
   snail as the picture, eyes emote, sprinkler water, sparrow. Risk: a wide shot may start close because the
   reference picture is a side-on medium shot; if so use the picture only for close/medium shots.
3. Assembly then fails on the test row (no narration_url): expected, it needs a music+effects track.
4. Fix stale notes (small): SHOW_BIBLE.md lines 14-15 and HANDOFF still say pip.png and "Do not rename it": change
   to refs/mimsi.png. SHOW_BIBLE has 1 leftover "Nori" and README.md has 2: replace with Mimsi.
5. Do NOT render all 40 shots until the test is judged.

## Open decisions and honest risks (told to the owner)
- YouTube monetization: inauthentic/mass-produced rules and extra scrutiny of AI kids content. Review every video
  by hand, upload Private first, publish a few polished different stories, not volume.
- Channel name: "Tiny Lawn Tales" was never checked on YouTube and does not contain the star's name. Owner may
  rename again (cheapest now). Mimsi collisions also not checked.
- Comedy that needs precise timing is hard for AI video; expect re-renders. Agnes credits/limits unknown.

## Not verified
Any render, Agnes credits/limits, whether the picture opens, YOUTUBE_READY value, TechPulse videos all Private,
which YouTube channel YT_REFRESH_TOKEN belongs to (check by uploading the first video as Private).

## Later
Music and sound effects (free sources) and rewrite assemble.py; make publish kid-safe (made-for-kids flag,
category, Private/unlisted first, description source); episodes 2-5; compilations of 4-5 episodes.
