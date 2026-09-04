# Input reference

Use a JSON object with `schema_version: 1`, a positive integer `n_qubits`, and exactly one of `gates`, `cubic_terms`, `ccz_atoms`, or `phase_terms`. An optional `name` may identify the example. Unknown fields and duplicate JSON keys are rejected.

Every qubit index is **zero-based**. A parity is a list of distinct indices: `[0, 3]` means `x0 + x3` over GF(2). A nonempty parity support represents a nonzero linear form; it does not assert that its value is one on every input bit string.

## 1. Gate list

```json
{
  "schema_version": 1,
  "n_qubits": 4,
  "gates": [
    {"gate": "cx", "qubits": [3, 0]},
    {"gate": "ccz", "qubits": [0, 1, 2]},
    {"gate": "cx", "qubits": [3, 0]}
  ]
}
```

Each gate object has exactly `gate` and `qubits` fields. Names are case-insensitive.

| Name | Qubits | Effect relevant to certification |
| --- | --- | --- |
| `cx`, `cnot` | `[control, target]` | XOR the control parity into the target |
| `swap` | `[a, b]` | Exchange wire parities |
| `ccz` | Three distinct wires | Add their alternating cubic interaction |
| `t`, `tdg` | One wire | Add one odd phase on the current parity |
| `x`, `z`, `s`, `sdg`, `id` | One wire | Free Clifford/affine changes |
| `cz` | Two distinct wires | Free Clifford phase |

The combined T/TDG contribution must have vanishing repeated-index signature entries. A lone T or CS-type target is outside the pure-cubic model. T and TDG have the same binary signature; their difference is Clifford. Affine constants introduced by X similarly affect only signs/global phases or Clifford corrections.

A nonidentity final CNOT/SWAP/X map is allowed and is not charged in phase T-count. Unsupported operations, including `h`, `ccx`, measurement, reset, and classical control, are rejected. Do not remove them to force the input into the accepted format: that would change the task being certified.

The tool reads this explicit JSON representation, not QASM text or framework-specific circuit objects. Export the supported gate list from your framework, or supply the fixed algebraic target below.

## 2. Cubic terms

```json
{
  "schema_version": 1,
  "n_qubits": 5,
  "cubic_terms": [[0, 1, 2], [0, 3, 4]]
}
```

A triple `[i,j,k]` is the coefficient-one monomial `xi*xj*xk` in the binary cubic form, equivalently the coordinate alternating atom. Its physical phase is `(-1)^(xi*xj*xk)`. The three indices must be distinct; their order does not matter. Duplicate triples cancel over GF(2).

## 3. Computed-parity CCZ interactions

```json
{
  "schema_version": 1,
  "n_qubits": 5,
  "ccz_atoms": [
    [[0], [1], [2]],
    [[0], [3], [4]]
  ]
}
```

Each interaction is a triple of parity supports. The three directions within an interaction must be linearly independent. Directions in different interactions may be dependent. The tool does not assume that the supplied number of interactions is minimal.

## 4. Phase terms

`phase_terms` defines the target through a list of odd parity phases:

```json
{
  "schema_version": 1,
  "n_qubits": 3,
  "phase_terms": [[0], [1], [2], [0,1], [0,2], [1,2], [0,1,2]]
}
```

This is a pure-cubic CCZ signature. The full tensor, including repeated-index entries, is computed and checked. Phase signs are irrelevant to this binary signature because they differ by Clifford corrections. Equal labels may appear and cancel in pairs at the signature level. Individual zero labels should be omitted.

## Supply an optimizer's witness

Any target form may also include:

- `ccz_witness`: a list in the same format as `ccz_atoms`.
- `phase_witness`: a list in the same format as `phase_terms`.

These fields are **candidates for the specified target**, not independently trusted data. A mismatch is an error. In particular, a phase witness must match all repeated-index entries as well as the distinct-index cubic entries.

A valid witness need not be optimal. The output distinguishes its original length from the certified optimum and records `certified_minimum_as_supplied`. The tool may find a shorter witness by cancelling repeated phases, shortening an even presentation, or using the CCZ conversion.

For example, [ccz_with_witness.json](../examples/ccz_with_witness.json) includes a seven-term phase witness. To recheck an exported certificate, supply its `phase_count.witness` as the `phase_witness` field alongside the original target.

Empty gate/term lists describe the zero target, whose phase and CCZ counts are both zero. Individual CCZ atoms still require three independent directions.

## Export a dense binary matrix

Parity supports are index lists, not rows of zero/one coefficients. If an optimizer returns one phase per row of a NumPy matrix, convert it with:

```python
phase_witness = [np.flatnonzero(row).tolist() for row in phase_matrix]
```

For a CCZ decomposition with shape `(m, 3, n_qubits)`:

```python
ccz_witness = [
    [np.flatnonzero(vector).tolist() for vector in triple]
    for triple in atom_matrix
]
```

NumPy is used only in this exporter; the resulting lists can be passed to the dependency-free certifier or written as JSON. If your phases are stored in columns, transpose the matrix first.

## Output and resource bounds

`phase_count` and `ccz_count` contain separate lower/upper bounds and exactness flags. A top-level `exact` verdict means the phase bounds meet; the CCZ bounds may still differ.

A JSON output includes a verified phase witness. It represents the correct signature up to a Clifford correction and does not include that correction as a synthesized gate sequence. The `pivot_relation`, when present, refers to zero-based interaction indices in the decomposition named by `phase_count.method`.

Full-signature checking scales cubically with the number of qubits. The default guard is 512 qubits; `--max-qubits N` or `certify(data, max_qubits=N)` changes that guard explicitly. This is a resource guard, not a mathematical validity limit.

The CLI's JSON certificate also records the input-file hash, tool-source hashes, version, and UTC creation time. The Python API returns deterministic mathematical results without file metadata or side effects.
