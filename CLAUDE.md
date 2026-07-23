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
success condition (e.g. "tracking stage runs with 0 failures on next pipeline run") —
don't stop at "I made a change that looks related."

## 5. No Unilateral Behavior Changes
Do not change pipeline behavior (auto-upload settings, approval gates, visibility/privacy
settings, cron schedules) without explicit confirmation first, even if it seems like an
obvious improvement. State the proposed change and wait for a yes.

## 6. Full Files, Not Diffs
This project's owner is a non-coder working by copy-paste. Every changed file must be
delivered as a complete file, never as a line-by-line diff or "change line X" instruction.

## 7. Verify Before Reporting Success
Do not report a fix as working, or a status as confirmed (e.g. "video is unlisted"),
without actually checking it. If it can't be verified, say so plainly instead of assuming.
