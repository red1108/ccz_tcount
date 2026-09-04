# Verification audit

During the manuscript consistency review on 2026-09-04, the earlier Waring verifier was found to compare only tensor entries with three distinct coordinate indices. That check alone does not validate a pure-cubic phase witness: residual linear or quadratic non-Clifford data can survive in repeated-index entries.

The verifier was corrected to require every repeated-index entry to vanish. Binary-value validation was also corrected to reject fractional entries instead of truncating them to integers. Regression tests cover:

1. The valid seven-term CCZ presentation.
2. An extra linear phase that leaves distinct-index cubic entries unchanged.
3. Extra quadratic non-Clifford data with zero first moments and unchanged distinct-index entries.
4. Fractional input that must not be accepted as binary.

All 60 released witnesses passed the stronger checks. The conclusions remained 47 exact phase counts and 13 targets not certified by these bounds. The records in this repository are fresh runs of the corrected verifier. They are not reconstructed transcripts of earlier scratch runs.

The 47 exact counts are tied to locally checked released witnesses. The separately cited VarTODD bounds remain literature inputs, not locally verified witnesses. Class U records a limitation of these checks, not evidence that a witness is non-optimal.
