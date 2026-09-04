PYTHON ?= python3

.PHONY: test reproduce check-records

test:
	$(PYTHON) -m unittest discover -s benchmarks -p 'test_verify_polytof.py' -v

reproduce:
	$(PYTHON) scripts/reproduce.py $(ARGS)

check-records:
	$(PYTHON) scripts/reproduce.py --check-records records/2026-09-04
