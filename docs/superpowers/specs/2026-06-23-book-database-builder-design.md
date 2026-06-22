# Book Database Builder — Design Spec

## Overview

A companion script to `sort_books.py` that scans directories recursively for book
files (PDF, EPUB, images), extracts embedded metadata, and builds/maintains a
persistent JSON database of the book collection with deduplication.

## CLI Interface

```
python3 build_book_db.py [--db books.json] /path/to/books [/path/to/more ...]
```

- Takes one or more directory paths as positional arguments
- `--db` sets output JSON path (default: `book_database.json`)
- Scans each directory recursively for supported file formats

## Pipeline

```
dir_path → os.walk → file list → extract_metadata() → normalize_name()
→ classify() → merge_entry() → save database
```

## JSON Schema

Single JSON file, a dict keyed by normalized book name:

```json
{
  "normalized_name": {
    "normalized_name": "A Biography of the Pixel",
    "raw_filenames": ["file1.pdf", "file2.epub"],
    "author": "Alvy Ray Smith",
    "publisher": null,
    "category": "Miscellaneous",
    "page_count": 352,
    "isbn": null,
    "file_size": 28456789,
    "file_path": "...",
    "format": "epub",
    "last_updated": "2026-06-23",
    "duplicate": true,
    "notes": null
  }
}
```

### Fields

| Field | Source | Notes |
|-------|--------|-------|
| `normalized_name` | `strip_metadata()` + `normalize_name()` | Primary key |
| `raw_filenames` | Filename from disk | Array; multiple = duplicate |
| `author` | Embedded metadata first, filename fallback | Never overwritten if populated |
| `publisher` | Embedded metadata | Never overwritten if populated |
| `category` | `classify()` from sort_books | Recalculated each run |
| `page_count` | PDF: PyMuPDF `page_count`; EPUB: estimate | |
| `isbn` | PDF subject/metadata regex | Never overwritten if populated |
| `file_size` | `os.stat().st_size` | |
| `file_path` | Full resolved path | Updated to latest copy |
| `format` | File extension lowercase | e.g. "pdf", "epub", "png" |
| `last_updated` | ISO date string | Always updated |
| `duplicate` | Boolean | True if >1 raw_filename |
| `notes` | Manual | Never overwritten |

## Supported Formats

- **PDF** — PyMuPDF (`fitz`): doc metadata (author, title, subject), page count
- **EPUB** — `ebooklib`: OPF metadata, spine-based page estimate
- **Images** — Pillow: dimensions, format, mode; no author/publisher
- **Other** (.azw3, .mobi, .djvu) — file size + extension only; metadata null

Unknown extensions are skipped with a warning.

## Metadata Extraction

Priority order for author/publisher: embedded doc metadata → filename parsing.
Extraction failures set field to `null` and continue (per-file warning printed).

## Deduplication

A duplicate is detected when:
1. **Normalized name match** — the same cleaned title already exists as a DB key
2. When matched, the new `raw_filename` is appended to `raw_filenames[]` and `duplicate` is set to `true`

Metadata from duplicates fills `null` fields in the existing entry but never
overwrites populated fields (preserving manual edits).

## Incremental Merge

On each run:
1. Load existing DB from `--db` path (or start empty)
2. Walk all directories, building a dict of normalized_name → metadata
3. For each entry: if key exists in DB → merge (fill nulls only); if not → insert
4. Report: `N new books, M duplicates, S skipped files`

## Dependencies

- `PyMuPDF` — PDF metadata extraction
- `ebooklib` — EPUB metadata extraction
- `Pillow` — Image metadata extraction
- Standard library: `os`, `re`, `sys`, `json`, `argparse`, `os.path`

## Task Breakdown for Implementation

1. Scaffold: create `build_book_db.py`, install deps, verify imports
2. Implement directory scanning (recursive, format-filtered)
3. Implement PDF metadata extraction via PyMuPDF
4. Implement EPUB metadata extraction via ebooklib
5. Implement image metadata extraction via Pillow
6. Adapt `normalize_name()` and `classify()` from `sort_books.py`
7. Implement JSON load/merge/save logic
8. Implement CLI argument parsing
9. Wire up main pipeline and test on both directories
