---
description: "The reuse ladder. Read before writing any new code."
---

# Ladder

Stop at the first rung that holds. Record it.

| Rung | Question | If yes |
|---|---|---|
| 0 | Does this need to exist for the locked ask? | Stop. No change. |
| 1 | Does this repo already do it? | Call it. |
| 2 | Does the stdlib do it? | Use it. |
| 3 | Does the platform already do it? | Use it. |
| 4 | Is the dependency already installed? | Use it. Do not add a second library. |
| 5 | Can it be one edit in an existing file? | Do that. |
| 6 | Only then | Minimum new code. |

A new abstraction needs two call sites that exist today. Validation stays at the boundary the repo already uses. Do not catch an error to hide it.
