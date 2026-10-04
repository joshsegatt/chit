---
name: chit
description: "Run a change from contract to a human report. Use when implementing, fixing, or vibe-coding in a git repo, and when the user wants the finished delivery. Not for greenfield repos with no commit, design systems, research-only questions, or writing a skill."
type: workflow
lifecycle: active
---

# Chit — the script commands the model

Any model. One move. Run `next`. Execute the `do` field exactly. Do not invent a parallel plan. The panel is five gates written by the script, not five personas.

## Loop

1. Run `next`. If it prints a start command, fill tier, locked sentence, non-goal, and for T1/T2 the exact test command plus `--oracle`, the taste the failing test must print. T2 also needs a rollback sentence. T3 stops.
2. Edit only what the locked sentence names. Test file separate from the fix. Read `references/ladder.md` before adding a file or dependency.
3. Run `next` again. Execute `do`. Repeat until `do` is `handoff`.
4. Hand the user `.chit/report.html`. Stop. Do not summarize over it.

## Commands

```bash
python3 scripts/chit.py next --repo . --label filter
python3 scripts/chit.py start --repo . --label filter --tier T1 --locked "fim exclusivo" --nongoal "nao mexe na UI" --test "python3 orders/filter_test.py"
python3 scripts/chit.py redgreen --repo . --label filter -- python3 orders/filter_test.py
python3 scripts/chit.py close --repo . --label filter
```

`next` is the only router. Close writes the report. Delivery is `ENTREGUE` plus panel all `PASS`.

## Panel

| Gate | Pass |
|---|---|
| escopo | ask has locked sentence and non-goal |
| risco | T2 has rollback; T3 never closes |
| mordida | red exit non-zero, green exit 0 |
| replay | verify re-ran both and printed CONFIRMED |
| higiene | smell scan has no block |

A model that skips a gate does not get `handoff`.

## Hard stops

- Do not run a command `next` did not print, except the edit itself.
- Do not write ask, receipt, or html by hand.
- Do not weaken the assertion to flip red into green.
- Do not claim delivery without `handoff`.

## When to read more

- Panel versus a model reviewer: `references/panel.md`
- Proof fence: `references/unfakeable.md`
- Tiers: `references/risk-tiers.md`
- Ladder: `references/ladder.md`
- Smells: `references/smells.md`
