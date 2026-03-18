.PHONY: help build-index build-older-release build-release-doc build-setup-doc build-help-admin-doc build-pdf build clean

MAIN_QMD := IPBES_Data_Vision.qmd
OLDER_RELEASES_QMD := older-releases.qmd
RELEASE_DOC_QMD := RELEASE.qmd
SETUP_DOC_QMD := setup.qmd
HELP_ADMIN_DOC_QMD := help_admin.qmd
PDF_PREFIX := IPBES-Data-Management-Vision
LATEST_PDF := _site/assets/IPBES-Data-Management-Vision-latest.pdf
RAW_VERSION := $(shell Rscript -e 'meta <- tryCatch(rmarkdown::yaml_front_matter("$(MAIN_QMD)"), error = function(e) list()); v <- meta$$version; if (is.null(v) || !nzchar(as.character(v))) v <- Sys.getenv("IPBES_VERSION", "development"); cat(as.character(v))')
NORM_VERSION := $(shell printf '%s' "$(RAW_VERSION)" | sed -E 's/^[Vv]//')
SAFE_VERSION := $(shell printf '%s' "v$(NORM_VERSION)" | sed 's/[^A-Za-z0-9._-]/-/g')
PDF_NAME := $(PDF_PREFIX)-$(SAFE_VERSION).pdf
PDF_PATH := build/$(PDF_NAME)

## help: Show available targets and their descriptions.
help:
	@awk '\
	/^## / { desc = substr($$0, 4); next } \
	/^[a-zA-Z0-9_.-]+:/ { \
		target = $$1; sub(/:.*/, "", target); \
		if (desc != "") { \
			sub("^" target ":[[:space:]]*", "", desc); \
			printf "%-20s %s\n", target, desc; \
			desc = ""; \
		} \
	}' $(MAKEFILE_LIST)

## build-index: Render the main living document to _site/index.html.
build-index:
	quarto render $(MAIN_QMD) --to html

## build-older-release: Render the all-releases page to _site/older-releases.html.
build-older-release:
	quarto render $(OLDER_RELEASES_QMD) --to html

## build-release-doc: Render hidden release process page to _site/release.html.
build-release-doc:
	quarto render $(RELEASE_DOC_QMD) --to html

## build-setup-doc: Render hidden template setup page to _site/setup.html.
build-setup-doc:
	quarto render $(SETUP_DOC_QMD) --to html

## build-help-admin-doc: Render hidden admin helper page to _site/help_admin.html.
build-help-admin-doc:
	quarto render $(HELP_ADMIN_DOC_QMD) --to html

## build-pdf: Render versioned PDF and update _site/assets/IPBES-Data-Management-Vision-latest.pdf.
build-pdf:
	mkdir -p build _site/assets
	if [ -n "$${IPBES_DOI:-}" ]; then \
		IPBES_BUILD_PDF=true quarto render $(MAIN_QMD) --to pdf --output "$(PDF_NAME)" --output-dir build -M "doi=$${IPBES_DOI}"; \
	else \
		IPBES_BUILD_PDF=true quarto render $(MAIN_QMD) --to pdf --output "$(PDF_NAME)" --output-dir build; \
	fi
	cp "$(PDF_PATH)" "$(LATEST_PDF)"

## build: Run all build targets (index, all-releases, hidden docs, and PDF).
build: build-index build-older-release build-release-doc build-setup-doc build-help-admin-doc build-pdf

## clean: Remove rendered outputs and temporary LaTeX/knitr files.
clean:
	rm -rf _site build
	find . -maxdepth 1 -type f \
		\( -name '*.tex' -o -name '*.knit.md' -o -name '*.aux' -o -name '*.toc' -o -name '*.out' -o -name '*.log' -o -name '*.lof' -o -name '*.lot' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.synctex.gz' \) -delete
