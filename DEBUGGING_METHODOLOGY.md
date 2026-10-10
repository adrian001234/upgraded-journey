# Debugging Methodology - Tiny Lawn Tales

This file exists because guessing at root causes wastes time and trust. The
person overseeing this pipeline (Zia) is not a coder and cannot verify a
guess himself. Every wrong diagnosis costs him trust and real time. This
standard makes that failure mode hard to repeat, for any agent (Claude or
otherwise) working on this repo.

## The rule, stated plainly

**Never state a root cause with confidence until it has been PROVEN by
execution or by a primary source, not just inferred by reading.** Reading
code and reasoning about what it "should" do is a hypothesis. Running the
exact code against real data, or reading the provider's own notice, and
observing the actual result, is evidence. Only evidence earns a confident
claim.

## The process, in order, every time

1. **Gather the real symptom first.** Pull the actual failed run's log
   output (the full error message, status code and traceback). Do not
   diagnose from a title or a one-line summary, because those describe the
   symptom, not the cause. If log access is not available, say so and ask
   for the log to be pasted in. Do not guess around the gap.

2. **Read the actual live code, not a memory of it, not a docstring's
   description of it, not a summary in a doc.** Fetch the file fresh every
   time. A docstring can claim something was fixed and still be wrong. The
   only ground truth is the code itself.

3. **Pull the actual live data the failing code was operating on** (the
   real Supabase row, the real API response, the real file content), not an
   imagined example of what that data probably looks like.

4. **Trace the code against that real data by hand, line by line**, if a
   full repro is not built yet. Write the trace down. Do not just assert the
   conclusion.

5. **Then actually run it** when the tooling allows. Copy the real function
   and the real data into a script, execute it, and compare the printed
   output to the real observed symptom. If they match, the hypothesis is
   confirmed by evidence. If they do not match, the hypothesis is wrong, so
   go back to step 1 and do not explain the mismatch away.

6. **Before proposing a fix, test the fix the same way.** Run the corrected
   code against the real failing data AND against at least one real working
   case, to confirm the fix resolves the failure without breaking what
   already works.

7. **Report findings with precision about what is proven and what is still
   uncertain.** If something is confirmed, say so plainly. If it is still a
   theory, say "unconfirmed" or "hypothesis". Never phrase a guess as a
   finding.

8. **Rule out alternative explanations explicitly**, especially the boring
   ones: a paused database, a retired model, a rate limit, a temporary
   outage. Confirm with live data or the provider's own notice before
   treating a single failed run as a code bug.

9. **Do not rush.** A wrong fix shipped fast is worse than a right fix
   shipped slowly. Try to disprove your own leading theory from more than
   one angle.

10. **Only after all of the above, take action** (write a fix, reset a
    status, revert a commit), and say in the commit message exactly what
    evidence supports it, so the next agent or Zia can see the reasoning and
    not only the result.

## What this looked like in practice (2026-10-10, Agnes model retirement)

- Symptom: two pipeline runs failed with HTTP 503 "model_not_found" for
  the video model agnes-video-v2.0. A 503 looks like a temporary outage, and
  the first guess was exactly that.
- What changed the diagnosis: instead of assuming an outage, the Agnes
  platform notifications page was read. It carried a notice saying
  agnes-video-v2.0 was retired on 2026-09-25 and that users must migrate to
  the Agnes Video 2.5 series. That is a primary source, not an inference.
- Result: the root cause was a retired model, not an outage, so waiting and
  retrying would never have worked. The video code was rewritten for
  agnes-video-2.5-flash with its new request format, then the live file was
  read back to confirm the change was really committed.
- Lesson: a status code is a clue, not a cause. Check the provider's own
  notices before calling something a temporary outage.

## Standing priority

This methodology takes priority over speed. Follow it before stating any
diagnosis as fact, and use code execution to verify a hypothesis whenever
the tooling allows it. Hand-tracing alone is not sufficient when execution
is available.
