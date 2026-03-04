args <- commandArgs(trailingOnly = TRUE)
mode <- if (length(args) > 0) args[[1]] else "local"

parse_bool <- function(x) {
  tolower(x) %in% c("1", "true", "yes", "y", "on")
}

run_quarto <- function(args, env = character()) {
  status <- system2("quarto", args = args, env = env)
  if (!identical(status, 0L)) {
    stop(sprintf("quarto command failed: quarto %s", paste(args, collapse = " ")), call. = FALSE)
  }
}

cleanup_intermediates <- function(input_files) {
  stems <- tools::file_path_sans_ext(basename(input_files))
  exts <- c(".knit.md", ".tex", ".aux", ".toc", ".out", ".log", ".lof", ".lot", ".fls", ".fdb_latexmk", ".synctex.gz")
  candidates <- unlist(lapply(stems, function(stem) paste0(stem, exts)), use.names = FALSE)
  existing <- unique(candidates[file.exists(candidates)])
  if (length(existing) > 0) {
    unlink(existing, force = TRUE)
  }
}

render_html <- function(input_file, output_name, output_dir, env = character()) {
  temp_out <- tempfile("quarto-html-")
  dir.create(temp_out, recursive = TRUE, showWarnings = FALSE)

  run_quarto(
    c("render", input_file, "--to", "html", "--output", output_name, "--output-dir", temp_out),
    env = env
  )

  src_html <- file.path(temp_out, output_name)
  if (!file.exists(src_html)) {
    stop(sprintf("Expected HTML output not found: %s", src_html), call. = FALSE)
  }
  file.copy(src_html, file.path(output_dir, output_name), overwrite = TRUE)

  dep_dir_name <- paste0(tools::file_path_sans_ext(basename(input_file)), "_files")
  src_dep_dir <- file.path(temp_out, dep_dir_name)
  if (dir.exists(src_dep_dir)) {
    dest_dep_dir <- file.path(output_dir, dep_dir_name)
    if (dir.exists(dest_dep_dir)) {
      unlink(dest_dep_dir, recursive = TRUE, force = TRUE)
    }
    file.copy(src_dep_dir, output_dir, recursive = TRUE)
  }
}

render_pdf <- function(input_file, output_name, output_dir, env = character()) {
  temp_out <- tempfile("quarto-pdf-")
  dir.create(temp_out, recursive = TRUE, showWarnings = FALSE)

  run_quarto(
    c("render", input_file, "--to", "pdf", "--output", output_name, "--output-dir", temp_out),
    env = env
  )

  src_pdf <- file.path(temp_out, output_name)
  if (!file.exists(src_pdf)) {
    stop(sprintf("Expected PDF output not found: %s", src_pdf), call. = FALSE)
  }
  file.copy(src_pdf, file.path(output_dir, output_name), overwrite = TRUE)
}

if (!file.exists("IPBES_Data_Vision.qmd")) {
  stop("Missing source file: IPBES_Data_Vision.qmd", call. = FALSE)
}
if (!file.exists("timeline.qmd")) {
  stop("Missing source file: timeline.qmd", call. = FALSE)
}
input_files <- c("IPBES_Data_Vision.qmd", "timeline.qmd")

output_dir <- Sys.getenv("IPBES_OUTPUT_DIR", unset = "html")
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
releases_dir <- file.path(output_dir, "releases")
dir.create(releases_dir, showWarnings = FALSE, recursive = TRUE)
assets_dir <- file.path(output_dir, "assets")
dir.create(assets_dir, showWarnings = FALSE, recursive = TRUE)

version <- Sys.getenv("IPBES_VERSION", unset = "development")
release_date <- substr(Sys.getenv("IPBES_RELEASE_DATE", unset = as.character(Sys.Date())), 1, 10)
doi <- Sys.getenv("IPBES_DOI", unset = "PENDING")
doi_url <- Sys.getenv("IPBES_DOI_URL", unset = "")
default_build_pdf <- if (mode %in% c("pr", "release")) "true" else "false"
build_pdf <- parse_bool(Sys.getenv("IPBES_BUILD_PDF", unset = default_build_pdf))

if (identical(doi_url, "") && !identical(doi, "PENDING")) {
  doi_url <- paste0("https://doi.org/", doi)
}

safe_version <- gsub("[^A-Za-z0-9._-]", "-", version)
pdf_name <- sprintf("IPBES-Data-Management-Vision-%s.pdf", safe_version)
latest_pdf_name <- "IPBES-Data-Management-Vision-latest.pdf"

quarto_env <- c(
  sprintf("IPBES_VERSION=%s", version),
  sprintf("IPBES_RELEASE_DATE=%s", release_date),
  sprintf("IPBES_DOI=%s", doi),
  sprintf("IPBES_DOI_URL=%s", doi_url),
  sprintf("IPBES_BUILD_PDF=%s", tolower(as.character(build_pdf)))
)

build_error <- NULL
tryCatch(
  {
    render_html("IPBES_Data_Vision.qmd", "index.html", output_dir, env = quarto_env)
    render_html("timeline.qmd", "timeline.html", output_dir, env = quarto_env)

    if (build_pdf) {
      render_pdf("IPBES_Data_Vision.qmd", pdf_name, releases_dir, env = quarto_env)
      file.copy(
        file.path(releases_dir, pdf_name),
        file.path(assets_dir, latest_pdf_name),
        overwrite = TRUE
      )
      stale_latest_in_releases <- file.path(releases_dir, latest_pdf_name)
      if (file.exists(stale_latest_in_releases)) {
        unlink(stale_latest_in_releases, force = TRUE)
      }
    }

    writeLines(
      c(
        sprintf("MODE=%s", mode),
        sprintf("OUTPUT_DIR=%s", output_dir),
        sprintf("BUILD_PDF=%s", tolower(as.character(build_pdf))),
        sprintf("VERSION=%s", version),
        sprintf("RELEASE_DATE=%s", release_date),
        sprintf("DOI=%s", doi),
        sprintf("PDF_NAME=%s", if (build_pdf) pdf_name else ""),
        sprintf("PDF_REL_PATH=%s", if (build_pdf) file.path("releases", pdf_name) else ""),
        sprintf("PDF_LATEST_REL_PATH=%s", if (build_pdf) file.path("assets", latest_pdf_name) else "")
      ),
      file.path(output_dir, "build-info.env")
    )

    if (build_pdf) {
      message(sprintf(
        "Build completed (%s): %s/index.html, %s/timeline.html, %s/%s",
        mode, output_dir, output_dir, releases_dir, pdf_name
      ))
    } else {
      message(sprintf(
        "Build completed (%s, HTML-only): %s/index.html, %s/timeline.html",
        mode, output_dir, output_dir
      ))
    }
  },
  error = function(e) {
    build_error <<- e
  },
  finally = {
    cleanup_intermediates(input_files)
  }
)

if (!is.null(build_error)) {
  stop(conditionMessage(build_error), call. = FALSE)
}
