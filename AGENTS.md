# Booksorter

Project with two Python scripts for managing a book collection.

## Scripts

### `sort_books.py` — Categorize books

Reads book filename lists, strips download-site metadata, and groups books into categories.

**Run**: `python3 sort_books.py` — reads `book_list.txt` and `book_list_2.txt`, outputs categorized groups to stdout

### `build_book_db.py` — Build JSON database (new)

Recursively scans directories for PDF/EPUB/image files, extracts embedded metadata, and maintains a JSON database with deduplication.

**Run**: `python3 build_book_db.py [--db books.json] /path/to/books [/path/to/more ...]`

**Dependencies**: `PyMuPDF`, `ebooklib`, `Pillow` (install with `pip3 install`)

**Database file**: `book_database.json` (default), keyed by normalized book name.

## Key files

- `sort_books.py` — categorizer (stdlib only). Entrypoint is `main()`.
- `build_book_db.py` — database builder (needs PyMuPDF, ebooklib, Pillow). Entrypoint is `main()`.
- `book_list.txt` / `book_list_2.txt` — input files for sort_books.py, one filename per line, optional `N:` prefix
- `book_database.json` — output of build_book_db.py
- `docs/superpowers/specs/2026-06-23-book-database-builder-design.md` — design spec
- `docs/superpowers/plans/2026-06-23-build-book-db-plan.md` — implementation plan

## Architecture (sort_books.py)

- `strip_metadata()` — regex-heavy cleanup of download-site artifacts (z-lib, Anna's Archive, ISBNs, etc.)
- `extract_clean_name()` — splits file extension, runs `strip_metadata`, strips leading numbers
- `classify()` — checks Bengali Unicode range first, then regex-matches against `CATEGORIES` keywords; falls back to "Miscellaneous"
- `normalize_name()` — strips parenthetical notes and punctuation from the clean name
- Output is printed to stdout only (no file write)

## Architecture (build_book_db.py)

- `scan_directory()` — recursive os.walk, yields (path, ext) for supported formats
- `extract_pdf_metadata()` — PyMuPDF: page_count, author, publisher from doc metadata; ISBN from subject/filename
- `extract_epub_metadata()` — ebooklib: author, publisher, ISBN from OPF metadata; spine-based page estimate
- `extract_image_metadata()` — Pillow: 1-page placeholder
- `extract_metadata()` — dispatches by file extension to the right extractor
- `build_entry()` — combines cleaned name (via sort_books), classification, and file metadata into a DB entry dict
- `merge_entry()` — incremental merge: fills nulls only, never overwrites populated fields, tracks duplicates
- `load_database()` / `save_database()` — JSON I/O with atomic save via tempfile+replace

## JSON schema (book_database.json)

Dict keyed by `normalized_name`. Each entry:
- `normalized_name`, `raw_filenames` (array), `author`, `publisher`, `category`,
  `page_count`, `isbn`, `file_size`, `file_path`, `format`, `last_updated`,
  `duplicate` (bool), `notes` (manual, never overwritten)

## Gotchas

- Bengali detection uses `\u0980-\u09FF` Unicode range check on the raw filename (before cleaning)
- Category keywords are regex patterns with `re.I` — be careful adding new patterns not to cause accidental matches across categories
- Many metadata-cleaning regexes are fragile; inspect output when adding new input sources
- `strip_metadata()` also strips HTML entities (`#x98;`), leading hex hash prefixes (`fa61f02_`), `[EARLY RELEASE]` tags, DOI brackets, `- libgen.li`, `- PDFDrive`, `.fdmdownload` suffixes, and trailing `(1)` duplicate markers
- The `-- Anna's Archive` suffix regexes are particularly convoluted — changing them might break cleanup for one format while fixing another
- `book_list.txt` has `N:` line number prefixes that are stripped before processing; `book_list_2.txt` does not
- `build_book_db.py` imports from `sort_books.py` for name cleaning and classification
- `build_book_db.py` author extraction uses embedded metadata first, filename fallback
- db fields `publisher`, `isbn`, `notes` are never overwritten once populated (preserves manual edits)
