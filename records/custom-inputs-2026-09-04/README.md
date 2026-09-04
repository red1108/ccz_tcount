# Custom-input interface validation

This record concerns the reusable `ccz_certify` interface added after the original benchmark snapshot. The original Polytof verifier and the two historical record directories were not modified.

- [report.json](report.json): all 60 published targets were supplied through the custom API as computed-parity CCZ atoms with a candidate phase witness. The API's output witness was independently checked by the original full-signature verifier. All checks passed and 47 phase counts were exact. Input files were matched against the pinned Git tree before the run and checked again afterward.
- [crosscheck.log](crosscheck.log): per-target bounds from that run.
- [tests.log](tests.log): 15 custom-interface tests and four original regression tests, including independent tensor and exhaustive small-circuit checks.
- [wheel-check.json](wheel-check.json): a regular wheel was installed in a separate environment without NumPy and invoked from outside the checkout. The exact example passed; the bounded example returned exit code 1 with `--require-exact`. The wheel included its MIT license.
- [validation.json](validation.json): aggregate status and source hashes.
- [SHA256SUMS](SHA256SUMS): hashes of these record files.

To repeat the data cross-check after installing the benchmark extra:

```sh
python scripts/check_custom_benchmarks.py .cache/polytof --output runs/custom-api-check.json
```

Use a fresh output filename. This cross-check has its own record schema; `scripts/reproduce.py --check-records` remains the checker for the historical benchmark record directories.
