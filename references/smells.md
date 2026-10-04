---
description: "Smells diff_smell.py flags. Read when it reports a finding."
---

# Smells

`scripts/diff_smell.py` scans added lines only.

| Code | Level | Meaning | What to do |
|---|---|---|---|
| `new-dep` | block | Manifest gained a dependency | Drop it or name the ladder rung that failed. |
| `new-file` | warn | File added | One-line reason, or fold it in. A new test file is fine. |
| `large-add` | warn | 80+ added lines | Cut to the locked sentence. |
| `placeholder` | block | TODO, FIXME, lorem, for now | Finish or move to `left out`. |
| `swallow` | block | Empty catch, `except: pass` | Propagate like the neighbor. |
| `type-escape` | block | `as any`, `@ts-ignore`, `type: ignore` | Fix the type. |
| `debug-leftover` | warn | `console.log`, `print(` outside tests | Remove. |
| `fake-data` | warn | example.com used as real outside tests | Use the repo fixture style. |

`block` is fixed or named in the receipt. A clean scan is not a passing test.
