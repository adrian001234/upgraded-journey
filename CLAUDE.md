# Project Instructions — Upgraded Journey (TechPulse)

These rules apply to every task in this repo. They exist because past sessions on this
and sibling projects (Marius, Nova) have hit real bugs and unwanted changes caused by
skipping them. Follow them even under time pressure.

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
When given a goal (e.g. "fix the tracking sync bug"), verify the fix against a concrete
success condition — don't stop at "I made a change that looks related."

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
without being asked. Given how many past bugs were "looked successful but wasn't," never
assume a paste succeeded cleanly.

## 10. Re-check the GitHub Write Block Periodically
Claude's GitHub write access (create_or_update_file) returns 403 here despite full
read/write showing on the connector — a known Anthropic-side bug, not a permissions
issue on this repo. Periodically retest it (try a trivial write); if it's been fixed,
drop the copy-paste workaround.

## 11. Read Every Pipeline-Adjacent File Before Changing Any One of Them
This pipeline is a chain: research -> script -> narration -> video -> assembly -> publish.
Each stage's code makes assumptions about the exact column names, status values, and JSON
shapes the stage before and after it uses. Before editing ANY one stage, pull the CURRENT
live content of the stage immediately before it and immediately after it (not from memory
of a prior session, not from what a previous chat summary says — the actual file, right
now) and confirm the status values / field names / data shapes still line up end to end.
Do the same Supabase schema check (actual live columns on video_pipeline, not an assumed
schema) before writing any code that reads or writes a new column.
This is not optional even for a "small" one-file fix — a change that looks correct in
isolation can silently break the handoff to the next stage if that stage was changed by a
different session since you last saw it. This exact failure happened on 2026-08-04/05: one
session introduced a separate `video_shots` table + `shots_pending` status while another
session, working from the already-established `shot_list`/`scripted`/`narrated` schema,
had no idea the first session's design existed — the two were incompatible until a later
session caught it by re-reading every file's live content instead of trusting either prior
session's notes.

## Known past incidents (do not repeat)
- Backup restore crashed on HTTP 400 from Supabase Storage (only 404 was handled). Fixed
  in db-backup.ts — readTarget() now treats 400 as "no backup found."
- FREEAPI_DB_BACKUP_KEY / ENCRYPTION_KEY must be exactly 64 hex characters. A 63-char key
  silently no-ops the backup instead of erroring loudly — always verify length before
  assuming it's correct.
- YT_REFRESH_TOKEN can be valid but scoped to the wrong YouTube channel if the wrong
  account was selected during OAuth. A working upload to the *wrong* channel (e.g.
  Erased instead of TechPulse Daily) looks like success in logs — always confirm which
  channel a token is authorized for, not just that it works.
- 2026-08-04/05: switching from 30-40s Shorts to long-form video, one session invented a
  `video_shots` table + `shots_pending` status for generate_script.py/generate_video.py
  without first reading narration/generate_narration.py or pipeline.yml's gate query, both
  of which already assumed a different, already-established schema (`shot_list` JSON on
  the pipeline row, `scripted`/`narrated`/`video_complete` statuses, ported from Marius).
  Result: two incompatible designs committed to main until a later session caught the
  mismatch by re-reading every adjacent file's live content (see Rule 11).

## Access notes
- GitHub write access via the Claude.ai connector is unreliable (403) even when the
  connector shows full read/write. Read access works — use it to pull full repo context
  (e.g. via Repomix) at the start of a session instead of asking the user to paste files.
- User has no terminal/SSH access — browser dashboards only (GitHub web editor, Render,
  Supabase). Never suggest local dev or CLI commands.

## How to work with the project owner
- He is a non-coder. He runs this project by talking Claude through it, step by step —
  he does not read or edit code himself.
- Give simple, step-by-step instructions. Perform the task, don't explain it at length.
  Minimal explanation — long write-ups waste his time and tokens.
- The goal each time is the end result (a working fix, a pasted file, a clicked button),
- not a lesson in how the code works.
- Every path, URL, or anything to be copied must be given in a copy-paste code block,
  no exceptions.
