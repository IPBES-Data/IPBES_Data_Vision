.PHONY: build build-pdf clean

build:
	Rscript scripts/build.R

build-pdf:
	IPBES_BUILD_PDF=true Rscript scripts/build.R

clean:
	rm -rf html site
	find . -maxdepth 1 -type f \
		\( -name '*.tex' -o -name '*.knit.md' -o -name '*.aux' -o -name '*.toc' -o -name '*.out' -o -name '*.log' -o -name '*.lof' -o -name '*.lot' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.synctex.gz' \) -delete
