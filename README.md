# ccz-certify

**Certify phase T-counts for your own CNOT/CCZ blocks.**

Give the tool a circuit, cubic target, or parity decomposition. It computes a lower bound, constructs a phase witness, and checks its full signature. When the bounds meet, you get an exact phase T-count. Otherwise, you get a verified interval and the witness supporting its upper bound.

This repository accompanies *Which CCZ Circuits Require the Most T Gates?* It also preserves the code and execution records behind **47 exact phase counts across 60 published benchmark targets**.

[Quick start](#quick-start) · [Input formats](docs/INPUT_FORMAT.md) · [How certificates work](docs/CERTIFICATES.md) · [Benchmark evidence](#reproduce-the-published-benchmarks)

## Quick start

Use Python 3.11 or newer. Clone the repository and install the local package:

```sh
git clone https://github.com/red1108/ccz_tcount.git
cd ccz_tcount
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ccz-certify examples/three_ccz_dependent.json --output runs/my-certificate.json
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead. The custom-circuit certifier uses only Python's standard library; NumPy is needed only for the published benchmark files.

Expected output:

```text
Phase T-count: 17 (exact)
CCZ count:     3 (exact)
Active dimension: 8
Verified phase witness: 17 terms
Scope: fixed pure-cubic phase target, up to free Clifford corrections.
```

The JSON certificate contains the bounds, a verified parity-phase witness, any merge-pivot relation used in that construction, and hashes identifying the input and tool source. Existing output files are preserved unless you pass `--force`.

You can also run `python -m ccz_certify ...` directly from the checkout.

## Put in your own circuit

Save this as `my-circuit.json`:

```json
{
  "schema_version": 1,
  "n_qubits": 3,
  "gates": [
    {"gate": "ccz", "qubits": [0, 1, 2]}
  ]
}
```

Then run:

```sh
ccz-certify my-circuit.json --output runs/my-circuit-certificate.json
```

This certifies a phase T-count of **7** and a CCZ count of **1**. Qubit indices start at zero. For a CNOT, `{"gate": "cx", "qubits": [control, target]}` gives the direction explicitly.

The circuit reader tracks parities through `cx`/`cnot` and `swap`, and accepts `ccz`, `x`, `z`, `s`, `sdg`, `cz`, and `id`. It also accepts `t` and `tdg` when their **combined full signature is pure cubic**. Hadamards, measurements, resets, and other unsupported operations produce an error rather than being dropped.

Already have an algebraic representation? Use `cubic_terms`, `ccz_atoms`, or `phase_terms` instead of `gates`. Optional `ccz_witness` and `phase_witness` fields let you check an optimizer's output or supply a better decomposition. See the [complete input reference](docs/INPUT_FORMAT.md).

## Understand the result

| Phase verdict | Meaning |
| --- | --- |
| `exact` | A verified witness meets the lower bound: the target's minimum phase T-count is certified. |
| `bounded` | The tool has valid lower and upper bounds, but has not proved the optimum. The minimum is odd for a nonzero target. |
| `unsupported` / `invalid` | The input is outside the implemented model, malformed, or contains a witness that fails verification. No certificate is issued. |

The top-level verdict concerns **phase T-count**. CCZ-count exactness is a separate field. A certified optimum for the target does not mean that every supplied gate list or witness is already optimal; `certified_minimum_as_supplied` records that distinction for optional witnesses.

Try the included examples:

| Input | Phase result | What it illustrates |
| --- | --- | --- |
| [One CCZ](examples/ccz.json) | **7**, exact | Minimal circuit input |
| [Three independent interactions](examples/three_ccz_independent.json) | **19**, exact | Full-rank case |
| [Three dependent interactions](examples/three_ccz_dependent.json) | **17**, exact | A relation involving all three interactions |
| [Computed parities](examples/computed_parities.json) | **11**, exact | Input after parity tracking |
| [A supplied phase witness](examples/ccz_with_witness.json) | **7**, exact | Check an existing synthesis result |
| [A remaining gap](examples/bounded.json) | **[13, 15]**, bounded | Valid bounds without an exact certificate |

For scripts and CI:

```sh
ccz-certify my-circuit.json --json
ccz-certify my-circuit.json --require-exact
```

Exit code `0` means a valid result was produced, including a bounded result. With `--require-exact`, a bounded result exits `1`. Invalid or unsupported inputs exit `2`.

### Scope

Certificates apply to **exact parity-phase synthesis of a fixed pure-cubic target**, with Clifford corrections and the final affine wire map free. All input bits are treated as independent variables; initialized-ancilla promises are not inferred. These certificates do not establish unrestricted Clifford+T optimality after introducing Hadamards, measurements, or different ancilla/gadget choices.

The exported witness is a list of parities carrying odd phases. It matches the target's full signature; a Clifford correction may still be needed to implement the original unitary. It is not a complete compiled gate sequence.

The method can close many bounds, but it is not a general tensor-rank solver. [The certificate method](docs/CERTIFICATES.md) explains exactly what each verdict proves.

## Use it from Python

```python
import json
from ccz_certify import certify

with open("my-circuit.json") as stream:
    result = certify(json.load(stream))

print(result["phase_count"]["lower_bound"])
print(result["phase_count"]["upper_bound"])
print(result["phase_count"]["witness"])
```

`certify()` performs the same checks as the CLI and raises `CertificateError` for invalid or unsupported inputs. It accepts ordinary Python lists and integers, and does not fetch data or write files. Binary matrices should first be converted to index-support lists as shown in the input reference. This makes it suitable for use after your own circuit generator or optimizer.

## Reproduce the published benchmarks

The original Polytof benchmark verifier and its recorded runs remain separate from the custom-input interface.

```sh
python -m pip install -e '.[benchmarks]'
python scripts/reproduce.py --compare records/2026-09-04
```

The runner fetches Polytof at the manifest's pinned commit, checks all 240 consumed files against that Git tree, runs the regression tests and 60 witness checks, and records a fresh run under `runs/`. You may supply an existing clean checkout with `--polytof /path/to/polytof`.

The reference result is **47 exact phase counts, 13 not certified by these bounds, and 35 certified CCZ counts**. The two separately reported VarTODD bounds are kept distinct from locally verified witnesses.

- [Reference run](records/2026-09-04/summary.md) and [fresh-checkout reproduction](records/2026-09-04-clean-checkout/summary.md).
- [All 60 results as JSON](records/2026-09-04/verification.json) or [CSV](records/2026-09-04/results.csv).
- [Regression-test log](records/2026-09-04/tests.log), [verifier log](records/2026-09-04/verification.log), and [run metadata](records/2026-09-04/run.json).
- [Input hashes and Git blob IDs](records/2026-09-04/inputs.json), [record checksums](records/2026-09-04/SHA256SUMS), and [source provenance](docs/SOURCES.md).
- [Verification details](benchmarks/README.md) and the [audit note about the repeated-index correction](docs/AUDIT.md).

Check the recorded evidence without downloading the upstream data:

```sh
make check-records
```

## Tests and license

```sh
python -m unittest discover -s tests -v
# With the benchmark extra installed:
make test
```

Tests cover exact and bounded examples, zero targets, unsupported gates, invalid witnesses, direct full-tensor comparisons, and exhaustive small-circuit checks up to Clifford corrections. The [custom-interface validation record](records/custom-inputs-2026-09-04/README.md) also cross-checks all 60 published targets and verifies an installation without NumPy.

The code is available under the [MIT license](LICENSE). Third-party benchmark files are fetched separately and retain their upstream license. Reuse the API in your own projects, and retain the required license notice when redistributing the code.
