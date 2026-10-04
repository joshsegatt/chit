---
description: "Senior review axes. Walk before the receipt on any T1+ change."
---

# Review bar

`CONFIRMED` is necessary, not sufficient.

| Axis | Pass | Reject |
|---|---|---|
| Purpose | One behavior. | Refactor mixed with the fix. |
| Caller | One real caller read. Contract unchanged, or the break is the ask. | New public function with no caller. |
| Bite | Test fails on `HEAD`, passes on the diff, verify agrees. | Assertion weakened to go green. Test and fix in one file. |
| Failure | Bad input follows the neighbor file. | New empty catch. |
| Compat | Default holds, or the receipt names who breaks. | Silent default change. Boolean mode flag. |
| Size | Non-test add under 80 lines, or the split is in `left out`. | New framework for one call site. |
