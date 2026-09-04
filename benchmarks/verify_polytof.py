#!/usr/bin/env python3
"""Verify active-dimension benchmark data against a pinned Polytof clone."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - depends on the caller's Python
    raise SystemExit(
        "numpy is required to read Polytof's .npy files. "
        "Use the Codex workspace Python or install numpy."
    ) from exc


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "polytof_manifest.json"
WITNESS_FILE_RE = re.compile(
    r"^(?P<tensor_id>\d{4})-(?P<length>\d{5})\.npy$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("polytof", type=Path, help="path to a local Polytof clone")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"benchmark manifest (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--suite",
        choices=("all", "standard25", "extended35"),
        default="all",
        help="suite to verify (default: all)",
    )
    parser.add_argument(
        "--format",
        choices=("table", "csv", "json"),
        default="table",
        help="result format (default: table)",
    )
    parser.add_argument(
        "--allow-commit-mismatch",
        action="store_true",
        help="run on a Polytof commit other than the pinned manifest commit",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"unsupported manifest schema in {path}")
    return manifest


def git_head(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def pair_index(i: int, j: int, n: int) -> int:
    """Index the pair (i,j), i<j, in lexicographic order."""
    if not 0 <= i < j < n:
        raise ValueError(f"invalid pair ({i}, {j}) for dimension {n}")
    return i * (2 * n - i - 1) // 2 + (j - i - 1)


def gf2_rank(columns: list[int]) -> int:
    """Rank over GF(2), with each matrix column packed into a Python int."""
    pivots: dict[int, int] = {}
    for value in columns:
        while value:
            pivot = value.bit_length() - 1
            if pivot in pivots:
                value ^= pivots[pivot]
            else:
                pivots[pivot] = value
                break
    return len(pivots)


def read_sparse_tensor(path: Path) -> tuple[int, list[tuple[int, int, int]]]:
    array = np.load(path, allow_pickle=False)
    if array.ndim != 2 or array.shape[1] != 3 or array.shape[0] < 2:
        raise ValueError(f"{path}: expected an (nnz+1)-by-3 sparse tensor")
    dims = tuple(int(x) for x in array[0])
    if dims[0] != dims[1] or dims[1] != dims[2]:
        raise ValueError(f"{path}: expected a cubic tensor, found {dims}")
    n = dims[0]
    triples = [tuple(int(x) for x in row) for row in array[1:]]
    if len(set(triples)) != len(triples):
        raise ValueError(f"{path}: duplicate sparse entries")
    for triple in triples:
        i, j, k = triple
        if not 0 <= i < j < k < n:
            raise ValueError(f"{path}: non-alternating sparse entry {triple}")
    return n, triples


def active_dimension(n: int, triples: list[tuple[int, int, int]]) -> int:
    """Rank of x -> i_x Theta from V to Lambda^2(V*)."""
    contractions = [0] * n
    for i, j, k in triples:
        contractions[i] ^= 1 << pair_index(j, k, n)
        contractions[j] ^= 1 << pair_index(i, k, n)
        contractions[k] ^= 1 << pair_index(i, j, n)
    return gf2_rank(contractions)


def released_length(directory: Path, tensor_id: str) -> tuple[int, Path]:
    matches: list[tuple[int, Path]] = []
    for path in directory.glob(f"{tensor_id}-*.npy"):
        match = WITNESS_FILE_RE.match(path.name)
        if match:
            matches.append((int(match.group("length")), path))
    if not matches:
        raise FileNotFoundError(
            f"no released witness file for {tensor_id} in {directory}"
        )
    if len(matches) != 1:
        names = ", ".join(path.name for _, path in sorted(matches))
        raise ValueError(
            f"expected one released witness file for {tensor_id}; found {names}"
        )
    return matches[0]


def binary_values(array: np.ndarray, path: Path) -> None:
    values = np.unique(array)
    if not np.all((values == 0) | (values == 1)):
        raise ValueError(f"{path}: expected binary data")


def load_witnesses(
    *, cp_path: Path, waring_path: Path, n: int, m: int, q: int
) -> tuple[np.ndarray, np.ndarray]:
    """Load one released CP witness and the released Waring witness."""
    cp = np.load(cp_path, allow_pickle=False)
    words = (n + 63) // 64
    expected_width = 3 * m * words
    if cp.ndim != 2 or cp.shape[0] < 1 or cp.shape[1] != expected_width:
        raise ValueError(
            f"{cp_path}: expected packed CP candidates with width {expected_width}, "
            f"found shape {cp.shape}"
        )
    if not np.issubdtype(cp.dtype, np.unsignedinteger):
        raise ValueError(f"{cp_path}: expected unsigned packed CP vectors")

    positions = np.arange(n, dtype=np.uint64)
    packed = cp[0].reshape(3 * m, words).astype(np.uint64, copy=False)
    cp_vectors = (
        (packed[:, positions // 64] >> (positions % 64)) & np.uint64(1)
    ).astype(np.uint8)

    waring = np.load(waring_path, allow_pickle=False)
    if waring.shape != (q, n):
        raise ValueError(
            f"{waring_path}: filename length/dimension predict {(q, n)}, "
            f"found {waring.shape}"
        )
    binary_values(waring, waring_path)
    return cp_vectors, waring.astype(np.uint8, copy=False)


def load_basis_transform(path: Path, n: int) -> np.ndarray:
    transform = np.load(path, allow_pickle=False)
    if transform.shape != (n, n):
        raise ValueError(
            f"{path}: expected an {n}-by-{n} basis transform, found {transform.shape}"
        )
    binary_values(transform, path)
    row_words = [
        sum(1 << int(j) for j in np.flatnonzero(transform[i])) for i in range(n)
    ]
    if gf2_rank(row_words) != n:
        raise ValueError(f"{path}: singular basis transform over GF(2)")
    return transform.astype(np.uint8, copy=False)


def pull_back_vectors(vectors: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """Return the released BCO-basis vectors in the original tensor basis."""
    # Every entry of this product is at most n (351 in the pinned suites), so
    # uint16 arithmetic cannot overflow before reduction modulo two.
    product = vectors.astype(np.uint16) @ transform.T.astype(np.uint16)
    return (product & np.uint16(1)).astype(np.uint8)


def coordinate_masks(vectors: np.ndarray) -> list[int]:
    """Pack the witness terms containing each coordinate into Python ints."""
    return [
        sum(1 << int(term) for term in np.flatnonzero(vectors[:, coordinate]))
        for coordinate in range(vectors.shape[1])
    ]


def verify_waring_signature(
    vectors: np.ndarray,
    n: int,
    target: set[tuple[int, int, int]],
    path: Path,
) -> None:
    """Match the full symmetric signature, including repeated indices.

    Pure-cubic targets are alternating: Sigma_iii and Sigma_iij must
    vanish. Checking only i<j<k would silently accept extra T or CS data.
    """
    masks = coordinate_masks(vectors)
    for i in range(n):
        if masks[i].bit_count() & 1:
            raise ValueError(
                f"{path}: Waring repeated-index signature mismatch at "
                f"({i}, {i}, {i}); expected 0, observed 1"
            )
        for j in range(i + 1, n):
            if (masks[i] & masks[j]).bit_count() & 1:
                raise ValueError(
                    f"{path}: Waring repeated-index signature mismatch at "
                    f"({i}, {i}, {j}); expected 0, observed 1"
                )
    for i in range(n - 2):
        mask_i = masks[i]
        for j in range(i + 1, n - 1):
            mask_ij = mask_i & masks[j]
            for k in range(j + 1, n):
                observed = (mask_ij & masks[k]).bit_count() & 1
                expected = int((i, j, k) in target)
                if observed != expected:
                    raise ValueError(
                        f"{path}: Waring cubic signature mismatch at "
                        f"({i}, {j}, {k}); expected {expected}, observed {observed}"
                    )


def verify_cp_signature(
    vectors: np.ndarray,
    n: int,
    target: set[tuple[int, int, int]],
    path: Path,
) -> None:
    u_masks = coordinate_masks(vectors[0::3])
    v_masks = coordinate_masks(vectors[1::3])
    w_masks = coordinate_masks(vectors[2::3])
    for i in range(n - 2):
        for j in range(i + 1, n - 1):
            for k in range(j + 1, n):
                observed = (
                    (u_masks[i] & v_masks[j] & w_masks[k]).bit_count()
                    + (u_masks[i] & v_masks[k] & w_masks[j]).bit_count()
                    + (u_masks[j] & v_masks[i] & w_masks[k]).bit_count()
                    + (u_masks[j] & v_masks[k] & w_masks[i]).bit_count()
                    + (u_masks[k] & v_masks[i] & w_masks[j]).bit_count()
                    + (u_masks[k] & v_masks[j] & w_masks[i]).bit_count()
                ) & 1
                expected = int((i, j, k) in target)
                if observed != expected:
                    raise ValueError(
                        f"{path}: CP cubic signature mismatch at ({i}, {j}, {k}); "
                        f"expected {expected}, observed {observed}"
                    )


def classify(m: int, d: int, q: int) -> str:
    if d == 3 * m and q == 6 * m + 1:
        return "C0"
    if d == 3 * m - 1 and q == 6 * m - 1:
        return "C1"
    if q == 2 * d + 1:
        return "L"
    return "U"


def verify_entry(polytof: Path, expected: dict) -> tuple[dict, list[str]]:
    tensor_id = expected["tensor_id"]
    errors: list[str] = []
    tensor_path = polytof / "data" / "tensors" / f"{tensor_id}.npy"
    transform_path = polytof / "data" / "paper" / "transform" / f"{tensor_id}.npy"
    cp_dir = polytof / "data" / "paper" / "cpd" / "topp"
    waring_dir = polytof / "data" / "paper" / "waring"

    n, triples = read_sparse_tensor(tensor_path)
    d = active_dimension(n, triples)
    m, cp_path = released_length(cp_dir, tensor_id)
    q, waring_path = released_length(waring_dir, tensor_id)
    cp_vectors, waring_vectors = load_witnesses(
        cp_path=cp_path, waring_path=waring_path, n=n, m=m, q=q
    )
    transform = load_basis_transform(transform_path, n)
    target = set(triples)
    verify_cp_signature(
        pull_back_vectors(cp_vectors, transform), n, target, cp_path
    )
    verify_waring_signature(
        pull_back_vectors(waring_vectors, transform), n, target, waring_path
    )
    category = classify(m, d, q)

    observed = {
        "suite": expected["suite"],
        "tensor_id": tensor_id,
        "name": expected["name"],
        "n": n,
        "nnz": len(triples),
        "m": m,
        "d": d,
        "lower_bound": 2 * d + 1,
        "q": q,
        "class": category,
        "q_certified": category != "U",
        "cp_signature_ok": True,
        "waring_signature_ok": True,
    }
    if "latest_q" in expected:
        observed["latest_q"] = expected["latest_q"]
        observed["latest_source"] = expected["latest_source"]

    for field in ("n", "m", "d", "q", "class"):
        if observed[field] != expected[field]:
            errors.append(
                f"{tensor_id} {field}: expected {expected[field]!r}, "
                f"observed {observed[field]!r}"
            )
    if q < observed["lower_bound"]:
        errors.append(
            f"{tensor_id}: released q={q} violates lower bound "
            f"{observed['lower_bound']}"
        )
    return observed, errors


def verify_summary(rows: list[dict], manifest: dict, suite: str) -> list[str]:
    errors: list[str] = []
    expected = manifest["expected_summaries"][suite]
    observed = summarize(rows)
    for field, value in expected.items():
        if observed[field] != value:
            errors.append(
                f"{suite} summary {field}: expected {value}, observed {observed[field]}"
            )
    return errors


def summarize(rows: list[dict]) -> dict[str, int]:
    counts = Counter(row["class"] for row in rows)
    return {
        "total": len(rows),
        "q_certified": sum(row["q_certified"] for row in rows),
        "C0": counts["C0"],
        "C1": counts["C1"],
        "L": counts["L"],
        "U": counts["U"],
    }


def print_table(rows: list[dict]) -> None:
    headers = ("suite", "id", "benchmark", "n", "m", "d", "2d+1", "q", "class")
    body = [
        (
            row["suite"],
            row["tensor_id"],
            row["name"],
            str(row["n"]),
            str(row["m"]),
            str(row["d"]),
            str(row["lower_bound"]),
            str(row["q"]),
            row["class"],
        )
        for row in rows
    ]
    widths = [max(len(headers[i]), *(len(row[i]) for row in body)) for i in range(len(headers))]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("  ".join("-" * width for width in widths))
    for row in body:
        rendered = []
        for i, value in enumerate(row):
            rendered.append(
                value.rjust(widths[i])
                if i in (3, 4, 5, 6, 7)
                else value.ljust(widths[i])
            )
        print("  ".join(rendered))


def print_csv(rows: list[dict]) -> None:
    fields = (
        "suite",
        "tensor_id",
        "name",
        "n",
        "nnz",
        "m",
        "d",
        "lower_bound",
        "q",
        "class",
        "q_certified",
        "cp_signature_ok",
        "waring_signature_ok",
    )
    print(",".join(fields))
    for row in rows:
        print(",".join(str(row[field]) for field in fields))


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    polytof = args.polytof.resolve()
    if not polytof.is_dir():
        raise SystemExit(f"not a directory: {polytof}")

    pinned = manifest["sources"]["polytof"]["commit"]
    head = git_head(polytof)
    commit_errors: list[str] = []
    if head is None:
        commit_errors.append(f"cannot read git HEAD from {polytof}")
    elif head != pinned:
        commit_errors.append(f"Polytof HEAD is {head}, expected pinned commit {pinned}")
    if commit_errors and not args.allow_commit_mismatch:
        for error in commit_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Use --allow-commit-mismatch to inspect a different revision.", file=sys.stderr)
        return 2

    expected_rows = manifest["benchmarks"]
    if args.suite != "all":
        expected_rows = [row for row in expected_rows if row["suite"] == args.suite]

    rows: list[dict] = []
    errors: list[str] = []
    for expected in expected_rows:
        try:
            observed, entry_errors = verify_entry(polytof, expected)
            rows.append(observed)
            errors.extend(entry_errors)
        except Exception as exc:  # report all broken instances in one run
            errors.append(f"{expected['tensor_id']}: {exc}")

    by_suite: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_suite[row["suite"]].append(row)
    for suite, suite_rows in by_suite.items():
        errors.extend(verify_summary(suite_rows, manifest, suite))

    summaries = {suite: summarize(suite_rows) for suite, suite_rows in by_suite.items()}
    if args.format == "json":
        print(
            json.dumps(
                {
                    "polytof_commit": head,
                    "pinned_commit": pinned,
                    "rows": rows,
                    "summaries": summaries,
                    "errors": errors,
                    "ok": not errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.format == "csv":
        print_csv(rows)
    else:
        print_table(rows)

    status_stream = sys.stdout if args.format == "table" else sys.stderr
    for suite in sorted(by_suite):
        summary = summaries[suite]
        print(
            f"SUMMARY {suite}: total={summary['total']} "
            f"q_exact={summary['q_certified']} C0={summary['C0']} "
            f"C1={summary['C1']} L={summary['L']} U={summary['U']}",
            file=status_stream,
        )

    if commit_errors:
        for error in commit_errors:
            print(f"WARNING: {error}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: witness lengths, full signatures, active dimensions, classes, "
        "and suite summaries match the manifest.",
        file=status_stream,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
