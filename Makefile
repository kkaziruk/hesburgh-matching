.PHONY: help match test clean

help:
	@echo "Hesburgh Lecture matching"
	@echo ""
	@echo "  make match   Build every plan from the CSVs in this folder into OUTPUTS/"
	@echo "  make test    Run the engine's tests"
	@echo "  make clean   Remove Python caches"
	@echo ""
	@echo "Details: README.md"

match:
	@python3 -m engine

test:
	@python3 -m unittest engine.tests.test_engine

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
