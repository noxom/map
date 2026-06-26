.PHONY: generate generate-force test

test:
	docker build -f Dockerfile.test -t map-test . -q
	docker run --rm map-test

generate:
	python3 scripts/generate_data.py

generate-force:
	python3 scripts/generate_data.py --force
