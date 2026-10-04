---
description: "Why a chit pass cannot be paraphrased. Read if you are about to claim the test passed."
---

# Unfakeable

Alibaba open-code-review splits the job: deterministic code decides what must not be wrong, the model only judges inside that fence. Chit takes the same cut on tests. The model picks the command. The script decides the verdict.

## What the agent cannot forge

- The receipt file. Only `scripts/chit.py` writes `.chit/<label>.json`.
- Red. A detached worktree at `HEAD` receives the test files and runs the command. Exit 0 is `DOES_NOT_BITE`.
- Green. The same worktree then receives the code files. Exit non-zero is `STILL_RED`.
- Verify. A second worktree at the recorded base re-runs both. File hashes in the receipt must still match the tree. Mismatch is `STALE`.
- Trivial commands (`echo`, `true`, `python -c` that only exits 0) are refused before any worktree.

## What this does not prove

- The test is the right product behavior. It proves this command fails on the base and passes on this diff.
- Flake-free forever. A second run that flips is a failed verify. Treat that as not passed.
- T3 safety. Migrations are out of scope.

## Same-file limit

If the assertion and the fix share a file, red cannot be isolated. Split them. That refusal is the point.
