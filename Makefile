.PHONY: build build-pdf clean

build:
	quarto render . --to html
	mkdir -p _site/releases
	if ls releases/*.pdf >/dev/null 2>&1; then cp releases/*.pdf _site/releases/; fi

build-pdf:
	mkdir -p releases _site/releases _site/assets
	RAW_VERSION=$$(Rscript -e 'meta <- tryCatch(rmarkdown::yaml_front_matter("IPBES_Data_Vision.qmd"), error = function(e) list()); v <- meta$$version; if (is.null(v) || !nzchar(as.character(v))) v <- Sys.getenv("IPBES_VERSION", "development"); cat(as.character(v))'); \
	NORM_VERSION=$$(printf '%s' "$$RAW_VERSION" | sed -E 's/^[Vv]//'); \
	SAFE_VERSION=$$(printf '%s' "v$$NORM_VERSION" | sed 's/[^A-Za-z0-9._-]/-/g'); \
	PDF_NAME="IPBES-Data-Management-Vision-$${SAFE_VERSION}.pdf"; \
	IPBES_BUILD_PDF=true quarto render IPBES_Data_Vision.qmd --to pdf --output "$$PDF_NAME" --output-dir releases; \
	quarto render . --to html; \
	mkdir -p _site/releases _site/assets; \
	cp releases/*.pdf _site/releases/; \
	cp "releases/$$PDF_NAME" "_site/assets/IPBES-Data-Management-Vision-latest.pdf"

clean:
	rm -rf _site html site
	find . -maxdepth 1 -type f \
		\( -name '*.tex' -o -name '*.knit.md' -o -name '*.aux' -o -name '*.toc' -o -name '*.out' -o -name '*.log' -o -name '*.lof' -o -name '*.lot' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.synctex.gz' \) -delete
