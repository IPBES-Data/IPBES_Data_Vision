.PHONY: help preview build admin clean

## help: Show available targets.
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //'

## preview: Live preview of the main document while editing.
preview:
	python3 scripts/release.py includes && quarto preview IPBES_Data_Vision.qmd

## build: Render the website (_site/) and the PDF (build/) as an unreleased draft.
build:
	python3 scripts/release.py build

## admin: Render the admin panel as one self-contained page: _site/admin/index.html.
admin:
	tmp=$$(mktemp -d) && cp admin.qmd $$tmp/index.qmd && (cd $$tmp && quarto render index.qmd --to html) \
	  && mkdir -p _site/admin && cp $$tmp/index.html _site/admin/index.html && rm -rf $$tmp

## clean: Remove rendered outputs and LaTeX leftovers.
clean:
	rm -rf _site build
	find . -maxdepth 1 -type f \( -name '*.tex' -o -name '*.log' -o -name '*.aux' \) -delete
