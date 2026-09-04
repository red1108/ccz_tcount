# Recorded benchmark verification

Completed: 2026-09-04T21:23:53+00:00 (UTC). Status: **PASS**.

All 60 released witnesses passed the full-signature checks.
**47 exact phase counts; 13 not certified by these bounds.**
The displayed CCZ count is also certified on 35 targets.

| Suite | Total | Exact phase counts | C0 | C1 | L | U |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| extended35 | 35 | 30 | 25 | 0 | 5 | 5 |
| standard25 | 25 | 17 | 8 | 2 | 7 | 8 |

Both subprocesses exited successfully: the four regression tests and the complete benchmark verifier.
Each of the 240 consumed upstream files matched the pinned Git blob before verification and was unchanged afterward.
The source-file hashes were also unchanged during the run.

The CSV separates released phase-witness lengths from the two literature-only upper bounds. Those external witnesses were not checked.
Exactness refers to the fixed pure-cubic phase targets and the model stated in the accompanying paper.

Source Git commit: `a93bf71ace84f66a31c72eba4c2f74a20a3779a9`.
Polytof commit: `1ab70261c749efe0be1d459ac00b7ffe2beb876e`.
