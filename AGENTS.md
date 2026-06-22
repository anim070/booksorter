# Booksorter

Python tools for managing a book collection.

## Scripts

### `python3 sort_books.py` — Categorize books

Reads `book_list.txt` / `book_list_2.txt` (one filename per line, `N:` prefixes stripped), strips download-site metadata, groups into categories. Output to stdout only. Stdlib only.

### `python3 build_book_db.py [--db books.json] /path/to/books [...]` — Build JSON database

Recursively scans for PDF/EPUB/image files, extracts embedded metadata (PyMuPDF, ebooklib, Pillow), merges into `book_database.json`. Imports `sort_books.py` for name cleaning. Incremental: reads DB on start, fills nulls only, never overwrites `publisher`/`isbn`/`notes`. Atomic save via tempfile+replace.

### `python3 search_web.py` — Flask + HTMX search webapp

Anna's Archive-style SPA that searches `book_database.json`. Needs `pip install flask`. Opens on http://127.0.0.1:5000.

## Key files

- `sort_books.py` — categorizer (stdlib). Entrypoint: `main()`.
- `build_book_db.py` — database builder (needs PyMuPDF, ebooklib, Pillow). Entrypoint: `main()`.
- `search_web.py` — Flask webapp (needs flask). Entrypoint: module-level `app.run()`.
- `book_database.json` — shared DB, 3.5K entries, in `.gitignore`
- `templates/` — `base.html`, `index.html`, `_results.html`, `detail.html` (Jinja2 + HTMX)
- `static/style.css` — Anna's Archive-inspired styles

## Architecture (sort_books.py)

- `strip_metadata()` — regex cleanup of z-lib, Anna's Archive, ISBNs, HTML entities, hex hashes, libgen, PDFDrive, `[EARLY RELEASE]`, DOI, `.fdmdownload`, `(1)` dup markers, etc.
- `extract_clean_name()` — strips extension, calls `strip_metadata`, strips leading numbers
- `classify()` — Bengali check (`\u0980-\u09FF`) on raw filename first, then regex CATEGORIES keywords; fallback "Miscellaneous"
- `normalize_name()` — strips parenthetical notes and punctuation
- `book_list.txt` has `N:` line prefix, `book_list_2.txt` does not

## Architecture (search_web.py)

- Routes: `GET /` (search page), `GET /search` (HTMX partial), `GET /book/<name>` (detail), `POST /book/<name>/open` (macOS Finder), `POST /book/<name>/copy-path`, `POST /book/<name>/notes` (form data, atomic write)
- Search: case-insensitive substring on `normalized_name`/`author`/`isbn`, filters by category/format/duplicate, sort by title/author/size/pages, 20 per page
- `open` uses `subprocess.run(["open", "-R", path])` — macOS only
- DB loaded at module level; `get_all_categories()` and `get_all_formats()` iterate all entries on every call
- HTMX CDN `@1.9.10` from unpkg, partial swaps on `#search-layout`
- Tags: toasts via `#toast` div, copy-path via JS `navigator.clipboard`

## JSON schema (book_database.json)

Dict keyed by `normalized_name`. Each entry: `normalized_name`, `raw_filenames` (array), `author`, `publisher`, `category`, `page_count`, `isbn`, `file_size`, `file_path`, `format`, `last_updated`, `duplicate` (bool), `notes`.

## Gotchas

- Bengali detection checks raw filename before any cleaning
- Category regex patterns use `re.I` — easy to accidentally overlap categories
- `strip_metadata()` regexes are fragile (Anna's Archive suffixes especially convoluted)
- `build_book_db.py` author: embedded metadata first, filename fallback
- DB fields `publisher`, `isbn`, `notes`: never overwritten once populated
- `notes` are stored as HTML-escaped by Jinja2 autoescape; textarea content renders escaped entities like `&amp;`
- Bare `except:` must not be used in notes save path (caught in review); use `except Exception:`
