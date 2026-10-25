---
name: sweep
description: Apply the same change across several jay-withers repositories, one PR per repo, and finish with a summary table. Use for estate-wide changes like bumping a shared workflow, adding a Makefile target everywhere, or aligning a convention.
argument-hint: <what to change> [repo ... | topic:<topic> | all]
---

# /sweep

Request: $ARGUMENTS

1. **Pick the targets.** Use the repos named, every repo carrying
   `topic:<topic>` in CATALOG.md, or `all`. If no target was given, work it
   out from the request (for example, by grepping `repos/*` for what needs
   changing). List the targets, and for each repo you're leaving out, say why
   in one line (it doesn't need the change, it's a template, it's archived).
   For more than 5 repos, confirm the list with the user before starting.
2. **Pilot on one repo first.** Run the full /change workflow on the simplest
   target. Wait until its checks go green. If the change turns out to be wrong
   or needs a different shape, adjust before multiplying it.
3. **Roll out** to the rest, one worktree each (`make task`), using the same
   branch name and the same PR title everywhere. Adapt to each repo's own
   conventions rather than pasting identical diffs. Skip local `make run` unless
   the change touches app code.
4. **Watch every PR's checks.** A failure in one repo doesn't block the
   others. Fix it in that repo's worktree, or report it. Merge each PR
   (`gh pr merge --squash`) once all its required checks pass, unless the user
   asked to leave them open; never `--admin`.
5. **Finish with a table**: repo | PR | checks | notes. Below it, list the
   skipped repos and any follow-ups.
