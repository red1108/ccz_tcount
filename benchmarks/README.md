# Polytof benchmark verification

This directory records and checks the benchmark calculations used in the
paper. The verifier reads Polytof's released sparse cubic tensors, CP
witnesses, Waring witnesses, and basis-change matrices. It independently
computes

$$
d=\operatorname{rank}_{\mathbb F_2}
\bigl(V\longrightarrow \Lambda^2V^*,\ x\longmapsto\iota_x\Theta\bigr)
$$

and checks every value against `polytof_manifest.json`. It also pulls the
released witness vectors back through Polytof's saved basis change and checks
their complete cubic signatures against the original sparse tensor. Thus the
lengths recorded below come from verified witnesses, not from treating a file
name as a certified rank. For CP witnesses, alternation makes every
repeated-index entry zero, so checking all distinct-index entries suffices.
For Waring witnesses, the verifier also checks that every repeated-index
entry vanishes: each coordinate occurs an even number of times, and every
pair of coordinates occurs together an even number of times. Only equality
of the full signature guarantees that the remaining correction is Clifford;
arbitrary linear and quadratic phase terms need not be Clifford.

`benchmark_tables.tex` contains the compact standard-suite table included by
the accompanying manuscript (not bundled here). Its entries follow the manifest below; the two later VarTODD upper
bounds are identified separately in the table and are not used as exact
certificates.

## Reproduce

Clone Polytof and check out the pinned revision:

```sh
git clone https://github.com/ZIB-IOL/polytof.git /path/to/polytof
git -C /path/to/polytof checkout 1ab70261c749efe0be1d459ac00b7ffe2beb876e
python3 benchmarks/verify_polytof.py /path/to/polytof
```

NumPy is the only non-standard Python dependency. It is needed only to read
the released `.npy` files; the GF(2) elimination itself uses Python integers.

The expected summaries are:

```text
SUMMARY extended35: total=35 q_exact=30 C0=25 C1=0 L=5 U=5
SUMMARY standard25: total=25 q_exact=17 C0=8 C1=2 L=7 U=8
PASS: witness lengths, full signatures, active dimensions, classes, and suite summaries match the manifest.
```

Use `--suite standard25` or `--suite extended35` for one suite. Machine-readable
output is available through `--format csv` and `--format json`.

Run `python3 -m unittest discover -s benchmarks -p 'test_verify_polytof.py'`
to check that added linear or quadratic non-Clifford data cannot pass the
full-signature verifier merely by preserving all distinct-index entries.

## Classification

- `C0`: `d = 3m` and the released phase witness has `q = 6m+1 = 2d+1`.
- `C1`: `d = 3m-1` and the released phase witness has `q = 6m-1 = 2d+1`.
- `L`: the released phase witness meets `q = 2d+1`, but is not `C0` or `C1`.
- `U`: these tests do not certify the released presentation as optimal.

Thus `C0`, `C1`, and `L` certify that `q` is the exact phase rank. In `C0` and
`C1`, the active-dimension bound also certifies that `m` is the exact CCZ
rank. Class `L` certifies only `q`; its `m` remains a CP-witness length. `U`
means only that the three checks above do not certify optimality; it is not
evidence that either released witness is non-optimal.

`standard25` uses the Polytof `08xx` compilation branch for 24 instances and
the `01xx` branch (`0117`) for QCLA Com_7. Polytof reports the best Waring
result across its two compilation branches, and the released `0117` phase
witness has length 59 whereas the released `0817` witness has length 63.
These are the 25 pure-cubic standard instances; the mixed-degree QFT4
instance is deliberately excluded. `extended35` consists of IDs
`0134`--`0168`: eight Cuccaro adders, seven chemistry basis-change instances,
seventeen Hamming-weight instances, and three unary-iteration instances.

The `m` field is the length of a released CP witness, and `q` is the length of
the released Waring witness. They are upper bounds until one of the displayed
lower bounds matches. For a CP file containing several candidates, the
verifier checks the first released candidate; all candidates have the same
length recorded in the filename. The manifest records the later VarTODD
values for Ham15 medium and high as provenance, but the verifier does not
treat an external reported count as a locally verified witness.

## Pinned sources

- Polytof: `1ab70261c749efe0be1d459ac00b7ffe2beb876e`
- Vandaele benchmark circuits: `231e6fe9f92d5bb1ebf7459c2a9233f5e74d148e`
- AlphaTensor-Quantum: `3def81a2a42666416a4a8041eea6e1bc98bc8e9f`
- VarTODD: `9c743e0e7440e6444d6f4a9230c51c1bdac6badb`

Only the Polytof revision is consumed by the verifier. The other revisions
record the provenance of the imported circuits and subsequent reported
counts.
