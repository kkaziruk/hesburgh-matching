.PHONY: help match test page parity clean

help:
	@echo "Hesburgh Lecture matching"
	@echo ""
	@echo "  make match   Build every plan from the CSVs in this folder into OUTPUTS/"
	@echo "  make test    Run the engine's tests"
	@echo "  make page    Rebuild web/index.html after changing web/ or the engine"
	@echo "  make parity  Check web/engine.js gives the same plans as the Python engine"
	@echo "  make clean   Remove Python caches"
	@echo ""
	@echo "Details: README.md"

match:
	@python3 -m engine

test:
	@python3 -m unittest engine.tests.test_engine

page:
	@python3 web/build_page.py --no-sample

parity:
	@node web/parity_check.js

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
