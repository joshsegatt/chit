---
description: "Why the panel is gates, not five model reviewers. Read if you are about to role-play experts."
---

# Panel

Alibaba open-code-review is a diff reviewer: deterministic code picks files, the model comments on lines. Chit does not beat that benchmark. It does a different job, and on that job the model is the weak part.

Five expert reviewers as prompts still lie in chorus. The panel is five gates the script sets to PASS or FAIL:

- escopo, the contract exists
- risco, T2 named a rollback, T3 did not close
- mordida, the test fails on HEAD and passes on the patch
- replay, a second worktree agreed
- higiene, the smell scan found no block

`next` is how any model is commanded. It prints one `do`. The model runs that string. When `do` is `handoff`, the html is the delivery. A paragraph is not.
