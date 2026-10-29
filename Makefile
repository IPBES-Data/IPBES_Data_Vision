.PHONY: help preview build clean

## help: Show available targets.
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //'

## preview: Live preview of the main document while editing.
preview:
	quarto preview IPBES_Data_Vision.qmd

## build: Render the website (_site/) and the PDF (build/) as an unreleased draft.
build:
	python3 scripts/release.py build

## clean: Remove rendered outputs and LaTeX leftovers.
clean:
	rm -rf _site build
	find . -maxdepth 1 -type f \( -name '*.tex' -o -name '*.log' -o -name '*.aux' \) -delete
