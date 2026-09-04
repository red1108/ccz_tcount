# Maintainer notes

The historical Polytof verifier and reference record files are preserved. The custom-input certifier is a separate package with its own tests; it does not rewrite those records.

Run the checks before changing the public contract:

```sh
python -m pip install -e '.[benchmarks]'
make test
make check-records
```

The custom-input tests include independent dense tensor comparisons and exhaustive small-circuit phase checks modulo Clifford corrections. Benchmark reproduction remains available through `scripts/reproduce.py`.

The repository is [red1108/ccz_tcount](https://github.com/red1108/ccz_tcount).
The `origin` remote points to this repository. After committing and checking changes, publish them with:

```sh
git push origin main
```
