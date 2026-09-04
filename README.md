# CCZ-to-T benchmark verification

Reproducible benchmark certificates accompanying **Which CCZ Circuits Require the Most T Gates?**

This repository contains the verifier, the 60-target benchmark manifest, regression tests, and a recorded run. It checks the released Polytof witnesses against the original tensors and computes active-dimension lower bounds. The recorded result is **47 exact phase counts and 13 targets not certified by these bounds**. It also certifies the displayed CCZ count on 35 targets.

The scope is exact phase synthesis of fixed pure-cubic targets. These certificates do not establish global optimality after changing Hadamard gadgets, measurements, feed-forward, or ancilla choices.

## Reproduce

Use Python 3.11 or newer. The recorded environment is Python 3.12.14 and NumPy 2.3.5.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/reproduce.py --compare records/2026-09-04
```

The runner fetches the public Polytof repository into `.cache/polytof`, checks out the exact commit in the manifest, verifies input-file contents against that Git tree, runs the regression tests and all 60 witness checks, and writes a new record under `runs/`. It compares numerical results and input hashes with the committed reference run. Timestamps and environment metadata may differ.

To reuse an existing clean checkout at the pinned commit:

```sh
python scripts/reproduce.py --polytof /path/to/polytof --compare records/2026-09-04
```

To choose a new output directory:

```sh
python scripts/reproduce.py --output runs/my-check
```

The runner refuses to overwrite an existing record. All saved commands use portable path labels; personal filesystem paths and hostnames are not included in the published records. A failed run is marked failed and retains its diagnostic logs.

## Inspect the recorded evidence

- [Run summary](records/2026-09-04/summary.md): aggregate results and verification scope.
- [Fresh-checkout reproduction](records/2026-09-04-clean-checkout/summary.md): a second run from a separate local Git clone, matching all results and input hashes.
- [Per-target JSON](records/2026-09-04/verification.json) and [CSV](records/2026-09-04/results.csv): all 60 witness lengths, active dimensions, bounds, and classifications.
- [Test log](records/2026-09-04/tests.log) and [verifier log](records/2026-09-04/verification.log): actual subprocess output and exit status in `run.json`.
- [Input provenance](records/2026-09-04/inputs.json): upstream paths, file sizes, SHA-256 hashes, and Git blob IDs for every consumed tensor, transform, and witness.
- [Run metadata](records/2026-09-04/run.json): UTC times, Python/NumPy versions, source commit, and source-file hashes.
- [SHA256SUMS](records/2026-09-04/SHA256SUMS): integrity hashes for the record files.

Check a saved record without downloading data:

```sh
python scripts/reproduce.py --check-records records/2026-09-04
```

Hashes identify the recorded bytes; independent reproduction checks the calculations.

## What is proved by the checks?

For a nonzero alternating target, the paper gives

$$2d+1 \le p(\Theta) \le 6c(\Theta)+1,\qquad d\le3c(\Theta).$$

Here `d` is the active dimension of the target, `m` is a released CCZ-witness length, and `q` is a released phase-witness length. Neither witness length is assumed minimal. A verified witness with `q = 2d+1` proves the exact phase count. If additionally `d = 3m` or `d = 3m-1`, the displayed CCZ count is also certified minimal.

| Class | Condition | Conclusion |
| --- | --- | --- |
| C0 | `d = 3m`, `q = 6m+1` | Exact phase and CCZ counts |
| C1 | `d = 3m-1`, `q = 6m-1` | Exact phase and CCZ counts |
| L | `q = 2d+1`, outside C0/C1 | Exact phase count |
| U | None of these equalities applies | These checks do not certify optimality |

The Waring verifier checks the **full symmetric signature**, including repeated-index entries. Matching only distinct-index cubic coefficients is insufficient. See [verification details](benchmarks/README.md) and the [audit note](docs/AUDIT.md).

The manifest separately records two literature upper bounds, 135 and 631, from VarTODD. Their witnesses are not validated by this repository and they do not contribute to the 47 exact certificates. The CSV keeps released and reported bounds in separate columns.

## Files

- `benchmarks/`: the code used for the paper, its manifest, regression tests, and the manuscript's table excerpt.
- `scripts/reproduce.py`: record generation, provenance checks, result comparison, and record-integrity checking.
- `records/`: committed reference evidence; each directory is one actual run.
- `runs/`, `.cache/`, `.venv/`: local generated material, excluded from Git.
- [Source provenance](docs/SOURCES.md) and [audit history](docs/AUDIT.md).

The full manuscript and third-party benchmark data are not bundled. Upstream data are retrieved at the recorded commit and retain their upstream license.

## Connect GitHub later

Create an empty GitHub repository, then run from this directory:

```sh
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

This local repository has no remote configured. Its existing history and evidence can be pushed as-is.
