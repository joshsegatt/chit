# chit

The test bites, or it did not ship.

Chit commands the coding agent. Any model. One next step. The script, not the model, decides if the change is delivered.

## What the dev gets

`.chit/report.html`. It says `ENTREGUE` only when five gates pass: scope, risk, bite, replay, hygiene. The red cause is on the page. A sentence from the agent is not a pass.

## Loop

```bash
python3 scripts/chit.py next --repo . --label filter
python3 scripts/chit.py start --repo . --label filter --tier T1 \
  --locked "fim exclusivo" --nongoal "nao mexe na UI" \
  --test "python3 orders/filter_test.py" --oracle "fim exclusivo"
python3 scripts/chit.py redgreen --repo . --label filter -- python3 orders/filter_test.py
python3 scripts/chit.py close --repo . --label filter
```

The agent should run `next` and execute the `do` field. `handoff` is the end.

T1 and T2 need `--oracle`. The failing test must print that string. If it does not, the verdict is `WRONG_BITE` and there is no report. Same output hash on red and green is `ENV_FAIL`.

## Install

Copy this folder into the skills directory of the agent. Keep `scripts/`.

| Agent | Path |
|---|---|
| Claude Code | `.claude/skills/chit` or `~/.claude/skills/chit` |
| Codex | `.codex/skills/chit` or `~/.codex/skills/chit` |
| Antigravity | `.agents/skills/chit` |
| VS Code Copilot agent mode | `.github/skills/chit` |

Needs git, Python 3, and a shell. A repo with at least one commit. Test and fix in different files.

## Not this

Chit does not review a diff for bugs nobody wrote a test for. That is a different tool. Chit proves this command fails on `HEAD` and passes on the patch, then writes the page.
