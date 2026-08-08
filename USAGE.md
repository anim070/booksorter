# Booksorter — Usage Guide

## sort_books.py — Categorize books

Groups book filenames into categories based on keyword matching.

```bash
# Default (reads book_list.txt and book_list_2.txt)
python3 sort_books.py

# Custom input files
python3 sort_books.py my_list.txt another_list.txt
```

No dependencies. Output is printed to stdout.

## build_book_db.py — Build JSON database

Scans directories recursively, extracts metadata from book files, and maintains a JSON database with deduplication.

### Install dependencies

```bash
pip3 install PyMuPDF ebooklib Pillow
```

### Basic usage

```bash
# Scan one directory
python3 build_book_db.py ~/EBooks

# Scan multiple directories
python3 build_book_db.py ~/EBooks /Volumes/SuperV/EBooks

# Specify custom database path
python3 build_book_db.py --db my_books.json ~/EBooks
```

### How it works

1. **Scans** directories recursively for `.pdf`, `.epub`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`
2. **Extracts** embedded metadata:
   - PDF: author, publisher, page count, ISBN via PyMuPDF
   - EPUB: author, publisher, page estimate, ISBN via ebooklib
   - Images: page count = 1 via Pillow
3. **Cleans & classifies** names using `sort_books.py` logic (filename metadata stripped, categories matched)
4. **Merges** incrementally into `book_database.json` — never overwrites populated fields
5. **Detects duplicates** by normalized name; tracks all raw filenames

### Incremental runs

The database is read on startup and new entries are merged on each run:

```bash
# First run — builds from scratch
python3 build_book_db.py ~/EBooks

# Second run — fast, merges existing entries (0 new, all duplicates)
python3 build_book_db.py ~/EBooks
```

## search_web.py — Search webapp

Flask + HTMX single-page app that searches the JSON database with an Anna's Archive-style interface.

### Install dependencies

```bash
pip3 install flask
```

### Usage

```bash
python3 search_web.py
```

Opens on http://127.0.0.1:5000.

### Features

- **Search**: case-insensitive by title, author, ISBN
- **Filters**: sidebar with category checkboxes, format checkboxes, hide-duplicates toggle
- **Sort**: by title, author, file size, page count
- **Pagination**: 20 results per page, HTMX-powered partial page loads
- **Book detail**: metadata table, "Open in Finder" (macOS), "Copy Path", editable notes
- **Notes**: saved back to `book_database.json` atomically, never overwritten by `build_book_db.py`

### JSON schema

Each entry in `book_database.json`:

| Field | Description |
|-------|-------------|
| `normalized_name` | Cleaned, deduplicated book name (dictionary key) |
| `raw_filenames` | All raw filenames that map to this book |
| `author` | From embedded metadata (null if unavailable) |
| `publisher` | From embedded metadata (never overwritten once set) |
| `category` | From sort_books.py keyword matching |
| `page_count` | PDF: exact; EPUB: estimate; Images: 1 |
| `isbn` | From metadata subject or filename |
| `file_size` | File size in bytes |
| `file_path` | Full path to the most recently scanned copy |
| `format` | File extension (pdf, epub, png, etc.) |
| `last_updated` | ISO date of last scan |
| `duplicate` | True if multiple raw_filenames exist |
| `notes` | Manual notes (never overwritten) |
