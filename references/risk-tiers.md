---
description: "Risk tiers T0-T3. Read when locking the ask, before editing."
---

# Risk tiers

Classify from the effect, not the diff size. A one-line auth change is T2.

| Tier | What it is | Owes |
|---|---|---|
| T0 | Copy, comment, docs, label. No branch changes behavior. | Smell scan. Show the new string. No chit. |
| T1 | Local logic. Callers keep the contract. | Test file separate from the fix. `BITES` then `CONFIRMED`. Caller named. |
| T2 | Boundary: HTTP, persisted field, authz, money, default users already depend on. | T1, plus rollback line written before the edit. |
| T3 | Migration, backfill, incompatible schema. | Stop. Split expand, backfill, switch. |

Rollback, one sentence, before the T2 edit:

- Code-only: revert of the file restores old behavior; no stored data changes.
- Stored data: new field is optional; old readers ignore it; no backfill here.
- Default flip: flag defaults off; this change only adds the branch.

If that sentence cannot be written, it is T3.
