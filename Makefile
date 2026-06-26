.PHONY: generate generate-force

generate:
	python3 scripts/generate_data.py

generate-force:
	python3 scripts/generate_data.py --force
