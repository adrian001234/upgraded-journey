# Project Instructions - Tiny Lawn Tales (repo: upgraded-journey)

These rules apply to every task in this repo. They exist because past sessions on
this project have hit real bugs and unwanted changes caused by skipping them.
Follow them even under time pressure.

Read SHOW_BIBLE.md (the show, Mimsi, the story rules) and PIPELINE.md (how it runs)
before writing shots or changing any stage.

## 1. Think Before Coding
Before writing or changing code, state the assumption being made out loud. If a request
is ambiguous (e.g. which pipeline stage, which script, which table), ask rather than
guessing. Do not silently pick an interpretation and run with it.

## 2. Simplicity First
Write the minimum code that solves the stated problem. No speculative features, no
extra abstraction, no "while I'm here" additions. If a fix can be 10 lines, it should
not be 100.

## 3. Surgical Changes
Edit only what the task requires. Do not refactor, rename, or "clean up" working code
as a side effect. Match the existing style of the file being edited. Do not remove or
alter comments/code you don't fully understand just because they look unrelated.

## 4. Goal-Driven Execution, Not Blind Imperatives
When given a goal (e.g. "fix the upload bug"), verify the fix against a concrete
success condition - don't stop at "I made a change that looks related."

## 5. No Unilateral Behavior Changes
Do not change pipeline behavior (auto-upload settings, approval gates, visibility/privacy
settings, cron schedules) without explicit confirmation first, even if it seems like an
obvious improvement. State the proposed change and wait for a yes.

## 6. Full Files, Not Diffs
This project's owner is a non-coder working by copy-paste. Every changed file must be
delivered as a complete file, never as a line-by-line diff or "change line X" instruction.

## 7. Verify Before Reporting Success
Do not report a fix as working, or a status as confirmed, without actually checking it.
If it can't be verified, say so plainly instead of assuming.

## 8. Check Access Before Recommending Tools
Before suggesting any external tool (Claude Code, TDD Guard, MCP servers, etc.), confirm
what access the user actually has (terminal/SSH? browser only?) in one line, before
selling the tool. Don't recommend an ideal solution the user can't reach.

## 9. Verify Every Paste Landed Correctly
After the user pastes a file in and commits, diff what's now live against what was given,
without being asked. Given how many past bugs were "looked successful but wasn't,"
never assume a paste succeeded cleanly. Check the file size and that the last lines
of the file are present, because a paste can be cut off partway.

## 10. Re-check the GitHub Write Block Periodically
Claude's GitHub write access (create_or_update_file) returns 403 here despite full
read/write showing on the connector (retested 2026-10-10, still blocked). Periodically
retest it (try a trivial write); if it's been fixed, drop the copy-paste workaround.
Likely cause (not confirmed): the connector is signed in as aliwaziri10, but the repo is
owned by adrian001234. A possible fix is for adrian001234 to add aliwaziri10 as a
collaborator with write access (repo Settings, Collaborators).

## 11. Read Every Pipeline-Adjacent File Before Changing Any One of Them
This pipeline is a chain: video -> assembly -> publish. Each stage's code makes
assumptions about the exact column names, status values, and JSON shapes the stage
before and after it uses. Before editing ANY one stage, pull the CURRENT live content of
the stage immediately before it and immediately after it (not from memory of a prior
session, not from what a previous chat summary says - the actual file, right now) and
confirm the status values / field names / data shapes still line up end to end.
Do the same Supabase schema check (actual live columns on video_pipeline, not an assumed
schema) before writing any code that reads or writes a new column.
This is not optional even for a "small" one-file fix.

## 12. Write Down Decisions In The Repo, Not Just In Chat
A previous session's full script was lost because it only existed in chat. Anything
that must survive (story, shot lists, character description, decisions) goes into
SHOW_BIBLE.md or PIPELINE.md.

## Known past incidents (do not repeat)
- YT_REFRESH_TOKEN can be valid but scoped to the wrong YouTube channel if the wrong
  account was selected during OAuth. A working upload to the *wrong* channel looks like
  success in logs - always confirm which channel a token is authorized for, not just
  that it works.
- One session invented a separate video_shots table and a shots_pending status without
  reading the adjacent stages, which already used a different schema (shot_list JSON on
  the pipeline row). Two incompatible designs sat on main until a later session re-read
  every adjacent file's live content (see Rule 11).
- 2026-10-10: the Supabase project was paused. SUPABASE_URL then stopped resolving
  ("Name or service not known") and looked like a bad secret. Check whether the
  project is paused before suspecting the secret.
- 2026-10-10: runs failed with HTTP 503 "model_not_found" and looked like an outage. The
  real cause was that Agnes retired agnes-video-v2.0 on 2026-09-25. Read the provider's
  notices before calling an error a temporary outage.
- The old auto-fixer (autoheal) patched single files with no cross-file awareness and
  caused schema mismatches. It was disabled and deleted on 2026-10-10. Do not rebuild it.

## Access notes
- GitHub write access via the Claude.ai connector is unreliable (403) even when the
  connector shows full read/write. Read access works.
- User has no terminal/SSH access - browser dashboards only (GitHub web editor,
  Supabase, YouTube Studio). Never suggest local dev or CLI commands.
- Spending rule across his channels: free tools only until the business makes $5,000.

## How to work with the project owner
- He is a non-coder. He runs this project by talking Claude through it, step by step -
  he does not read or edit code himself.
- ONE step at a time. Wait for him to report back before the next step.
- Simple, click-by-click instructions. Perform the task, don't explain it at length.
- Every path, URL, name, value or file to be copied goes in its own copy-paste code
  block, no exceptions (never in a table).
- Be proactive: don't ask "should I?" for straightforward next steps. Do disagree with
  him when he is wrong - he asked for that.
- The goal each time is the end result (a working fix, a pasted file, a clicked button),
  not a lesson in how the code works.
