.PHONY: generate generate-force collect collect-force test

BASE_DIR ?=
MAX_PX  ?= 1024

test:
	docker build -f Dockerfile.test -t map-test . -q
	docker run --rm map-test

generate:
	python scripts/generate_data.py

generate-force:
	python scripts/generate_data.py --force

collect:
	python scripts/collect_places.py $(if $(BASE_DIR),"$(BASE_DIR)") --max-px $(MAX_PX)

collect-force:
	python scripts/collect_places.py $(if $(BASE_DIR),"$(BASE_DIR)") --max-px $(MAX_PX) --force
