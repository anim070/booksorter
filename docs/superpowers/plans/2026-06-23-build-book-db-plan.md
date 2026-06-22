# Book Database Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a single-file Python script that recursively scans book directories, extracts metadata from PDF/EPUB/image files using PyMuPDF/ebooklib/Pillow, and maintains a JSON database with deduplication.

**Architecture:** Single `build_book_db.py` file mirroring `sort_books.py`'s pattern. Imports `strip_metadata`, `normalize_name`, `classify`, and `CATEGORIES` from `sort_books.py`. Format-specific metadata extractors dispatch by file extension. JSON database is keyed by normalized name for natural dedup. Incremental merge never overwrites populated fields.

**Tech Stack:** Python 3 stdlib + PyMuPDF, ebooklib, Pillow

---

### Task 1: Dependencies & Imports + CLI Scaffold

**Files:**
- Create: `build_book_db.py`
- Read: `sort_books.py` (for import reference)

- [ ] **Step 1: Write the file scaffold with imports and argparse**

```python
#!/usr/bin/env python3
"""
build_book_db.py — recursively scan directories for book files, extract
metadata, and maintain a JSON database with deduplication.

Usage:
    python3 build_book_db.py [--db books.json] /path/to/books [/path/to/more ...]

Dependencies: PyMuPDF, ebooklib, Pillow (pip install).
"""

import argparse
import json
import os
import re
import sys
from datetime import date

from sort_books import CATEGORIES, strip_metadata, normalize_name, classify


SUPPORTED_EXTENSIONS = {'.pdf', '.epub', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build/maintain a JSON book database from book directories."
    )
    parser.add_argument("--db", default="book_database.json",
                        help="Path to JSON database file (default: book_database.json)")
    parser.add_argument("directories", nargs="+",
                        help="One or more book directories to scan recursively")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Scanning {len(args.directories)} director{'y' if len(args.directories) == 1 else 'ies'}...")
    for d in args.directories:
        if not os.path.isdir(d):
            print(f"Warning: not a directory, skipping: {d}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify imports work**

Run: `python3 -c "from sort_books import CATEGORIES, strip_metadata, normalize_name, classify; print('imports OK')"`
Expected: `imports OK`

Run: `python3 build_book_db.py --help`
Expected: help text showing `--db` and `directories` args

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: scaffold build_book_db.py with imports and CLI"
```

---

### Task 2: Directory Scanning with File Dispatch

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write the recursive file scanner**

Add to `build_book_db.py`, above `main()`:

```python
def scan_directory(root_dir):
    """Yield (filepath, ext) for every supported book file under root_dir."""
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                yield os.path.join(dirpath, fname), ext
```

- [ ] **Step 2: Update main() to test the scanner**

Replace the `main()` body with:

```python
def main():
    args = parse_args()
    all_files = []
    for d in args.directories:
        if not os.path.isdir(d):
            print(f"Warning: not a directory, skipping: {d}")
            continue
        for fp, ext in scan_directory(d):
            all_files.append((fp, ext))
    print(f"Found {len(all_files)} book files")
```

- [ ] **Step 3: Test the scanner**

Run: `python3 build_book_db.py --db /dev/null ~/EBooks 2>&1 | head -5`
Expected: prints "Found N book files" (N will be large since the directory has many files)

- [ ] **Step 4: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add recursive directory scanner for supported formats"
```

---

### Task 3: PDF Metadata Extraction

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write PDF extractor**

Add to `build_book_db.py`:

```python
def extract_pdf_metadata(filepath):
    """Extract metadata from a PDF using PyMuPDF."""
    import fitz
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        doc = fitz.open(filepath)
        result["page_count"] = doc.page_count
        meta = doc.metadata or {}
        result["author"] = meta.get("author") or None
        # publisher sometimes in subject or producer field
        result["publisher"] = meta.get("publisher") or None
        if not result["publisher"]:
            result["publisher"] = meta.get("producer") or None
        # ISBN often in subject or as a separate metadata field
        subject = meta.get("subject", "") or ""
        isbn_match = re.search(r'(?:ISBN[:\s]*)?(\d{13}|\d{9}[\dXx])', subject)
        if isbn_match:
            result["isbn"] = isbn_match.group(1)
        # Also check filename for ISBN
        if not result["isbn"]:
            fname = os.path.basename(filepath)
            isbn_match = re.search(r'(\d{13}|\d{9}[\dXx])', fname)
            if isbn_match:
                result["isbn"] = isbn_match.group(1)
        doc.close()
    except Exception as e:
        print(f"  [WARN] PDF extraction failed: {filepath} — {e}", file=sys.stderr)
    return result
```

- [ ] **Step 2: Quick test on one PDF**

Run: `python3 -c "
import build_book_db
fp = '/Users/ahsan/EBooks/10290.pdf'
r = build_book_db.extract_pdf_metadata(fp)
print(r)
"`
Expected: `{'page_count': N, 'author': None, 'publisher': None, 'isbn': None}`

Also test an Anna's Archive style PDF:
Run: `python3 -c "
import build_book_db
fp = '/Users/ahsan/EBooks/13 Things That Don\\''t Make Sense ... -- Anna.s Archive.pdf' 2>/dev/null || fp='/Users/ahsan/EBooks/A Biography of the Pixel (Alvy Ray Smith)2021_--_-- (Z-Library).epub'
print(fp)
"`
Skip if neither file exists — the exact filename depends on the actual listing.

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add PDF metadata extractor via PyMuPDF"
```

---

### Task 4: EPUB Metadata Extraction

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write EPUB extractor**

Add to `build_book_db.py`:

```python
def extract_epub_metadata(filepath):
    """Extract metadata from an EPUB using ebooklib."""
    import ebooklib
    from ebooklib import epub
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        book = epub.read_epub(filepath)
        # Title
        title = book.get_metadata('DC', 'title')
        # Author
        creators = book.get_metadata('DC', 'creator')
        if creators:
            result["author"] = creators[0][0]
        # Publisher
        publishers = book.get_metadata('DC', 'publisher')
        if publishers:
            result["publisher"] = publishers[0][0]
        # ISBN from metadata or identifier
        identifiers = book.get_metadata('DC', 'identifier')
        for ident in identifiers:
            val = ident[0]
            isbn_match = re.search(r'(?:ISBN[:\s]*)?(\d{13}|\d{9}[\dXx])', val)
            if isbn_match:
                result["isbn"] = isbn_match.group(1)
                break
        # Page count: count items in spine as rough estimate
        spine_count = len(list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)))
        if spine_count > 0:
            result["page_count"] = spine_count
    except Exception as e:
        print(f"  [WARN] EPUB extraction failed: {filepath} — {e}", file=sys.stderr)
    return result
```

- [ ] **Step 2: Test on an EPUB file**

Run: `python3 -c "
import build_book_db
fp = '/Users/ahsan/EBooks/A Biography of the Pixel (Alvy Ray Smith)2021_--_-- (Z-Library).epub'
r = build_book_db.extract_epub_metadata(fp)
print(r)
"`
Expected: author and spine-count page estimate (may be None for some fields, that's fine)

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add EPUB metadata extractor via ebooklib"
```

---

### Task 5: Image Metadata Extraction

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write image extractor**

Add to `build_book_db.py`:

```python
def extract_image_metadata(filepath):
    """Extract dimensions and format from an image using Pillow."""
    from PIL import Image
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        with Image.open(filepath) as img:
            w, h = img.size
            result["page_count"] = 1  # single image = 1 "page"
            # Store dimensions in a note-like way via author field isn't right — leave null
    except Exception as e:
        print(f"  [WARN] Image extraction failed: {filepath} — {e}", file=sys.stderr)
    return result
```

- [ ] **Step 2: Test on a PNG**

Run: `python3 -c "
import build_book_db
fp = '/Users/ahsan/EBooks/48792_ingenuity_poster-vertical.png'
r = build_book_db.extract_image_metadata(fp)
print(r)
"`
Expected: `{'page_count': 1, 'author': None, 'publisher': None, 'isbn': None}`

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add image metadata extractor via Pillow"
```

---

### Task 6: Main Extraction Dispatch

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write the dispatch function**

Add to `build_book_db.py`:

```python
FORMAT_EXTRACTORS = {
    ".pdf": extract_pdf_metadata,
    ".epub": extract_epub_metadata,
    ".png": extract_image_metadata,
    ".jpg": extract_image_metadata,
    ".jpeg": extract_image_metadata,
    ".gif": extract_image_metadata,
    ".bmp": extract_image_metadata,
    ".tiff": extract_image_metadata,
    ".webp": extract_image_metadata,
}


def extract_metadata(filepath, ext):
    """Dispatch to the right extractor based on file extension."""
    extractor = FORMAT_EXTRACTORS.get(ext)
    if extractor is None:
        return {"page_count": None, "author": None, "publisher": None, "isbn": None}
    return extractor(filepath)
```

- [ ] **Step 2: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add format dispatch for metadata extraction"
```

---

### Task 7: Build Entry from File + Name Normalization

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write the entry builder**

Add to `build_book_db.py`:

```python
def build_entry(filepath, ext):
    """Build a book database entry dict from a file."""
    fname = os.path.basename(filepath)
    # Strip N: prefix if present (legacy book_list format)
    raw = re.sub(r'^\d+:\s*', '', fname)

    # Extract clean name and normalize
    from sort_books import extract_clean_name
    cleaned, _ = extract_clean_name(raw)
    normalized = normalize_name(cleaned)
    category = classify(normalized, raw)

    # Extract file metadata
    meta = extract_metadata(filepath, ext)
    file_size = os.path.getsize(filepath)

    return {
        "normalized_name": normalized,
        "raw_filenames": [raw],
        "author": meta["author"],
        "publisher": meta["publisher"],
        "category": category,
        "page_count": meta["page_count"],
        "isbn": meta["isbn"],
        "file_size": file_size,
        "file_path": filepath,
        "format": ext.lstrip("."),
        "last_updated": date.today().isoformat(),
        "duplicate": False,
        "notes": None,
    }
```

- [ ] **Step 2: Quick test**

Run: `python3 -c "
import build_book_db
fp = '/Users/ahsan/EBooks/10290.pdf'
e = build_book_db.build_entry(fp, '.pdf')
print(e['normalized_name'])
print(e['author'], e['page_count'])
"`
Expected: clean normalized name, metadata extracted from file

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add entry builder with name normalization and classification"
```

---

### Task 8: JSON Database Load/Merge/Save

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Write database load/merge/save functions**

Add to `build_book_db.py`:

```python
def load_database(db_path):
    """Load existing database from JSON, or return empty dict."""
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"Loaded {len(data)} existing entries from {db_path}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not load {db_path} — {e}", file=sys.stderr)
    return {}


def merge_entry(db, entry):
    """Merge a new entry into the database.

    If the normalized_name already exists, merge: append raw_filename,
    fill null fields, set duplicate flag. Never overwrite populated fields.
    """
    key = entry["normalized_name"]
    if key in db:
        existing = db[key]
        # Append raw filename if new
        raw = entry["raw_filenames"][0]
        if raw not in existing["raw_filenames"]:
            existing["raw_filenames"].append(raw)
        # Mark duplicate
        existing["duplicate"] = len(existing["raw_filenames"]) > 1
        # Fill null fields
        for field in ("author", "publisher", "isbn", "notes"):
            if existing.get(field) is None and entry.get(field) is not None:
                existing[field] = entry[field]
        # Update page_count if previously null
        if existing.get("page_count") is None and entry.get("page_count") is not None:
            existing["page_count"] = entry["page_count"]
        # Always update category, file_size, file_path, format, last_updated
        existing["category"] = entry["category"]
        existing["file_size"] = entry["file_size"]
        existing["file_path"] = entry["file_path"]
        existing["format"] = entry["format"]
        existing["last_updated"] = entry["last_updated"]
        return False  # duplicate/merge
    else:
        db[key] = entry
        return True  # new entry


def save_database(db, db_path):
    """Write database to JSON file."""
    tmp_path = db_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, db_path)
    print(f"Saved {len(db)} entries to {db_path}")
```

- [ ] **Step 2: Commit**

```bash
git add build_book_db.py
git commit -m "feat: add database load/merge/save with incremental merge"
```

---

### Task 9: Wire Up Main Pipeline

**Files:**
- Modify: `build_book_db.py`

- [ ] **Step 1: Replace main() with full pipeline**

```python
def main():
    args = parse_args()

    db = load_database(args.db)
    new_count = 0
    dup_count = 0
    skip_count = 0
    total_files = 0

    for d in args.directories:
        if not os.path.isdir(d):
            print(f"Warning: not a directory, skipping: {d}")
            continue
        print(f"\nScanning: {d}")
        for filepath, ext in scan_directory(d):
            total_files += 1
            try:
                entry = build_entry(filepath, ext)
                is_new = merge_entry(db, entry)
                if is_new:
                    new_count += 1
                else:
                    dup_count += 1
                print(f"  {'+' if is_new else '~'} {entry['normalized_name']}"
                      f"  ({ext})")
            except Exception as e:
                print(f"  [ERR] {filepath} — {e}", file=sys.stderr)
                skip_count += 1

    save_database(db, args.db)
    print(f"\n{'='*50}")
    print(f"  Total files scanned: {total_files}")
    print(f"  New entries:         {new_count}")
    print(f"  Duplicates merged:   {dup_count}")
    print(f"  Skipped (errors):    {skip_count}")
    print(f"  Database entries:    {len(db)}")
    print(f"{'='*50}")
```

- [ ] **Step 2: Run it on a small directory first**

Run: `python3 build_book_db.py --db /tmp/test_books.json /Users/ahsan/EBooks 2>&1 | tail -20`
Expected: runs to completion, prints summary stats, saves JSON

- [ ] **Step 3: Commit**

```bash
git add build_book_db.py
git commit -m "feat: wire up full pipeline — scan, extract, merge, save"
```

---

### Task 10: Verify and Tweak

**Files:**
- Run: `build_book_db.py` on both directories

- [ ] **Step 1: Run full scan on both directories**

Run: `python3 build_book_db.py --db book_database.json ~/EBooks /Volumes/SuperV/EBooks 2>&1`
Expected: scans both directories, processes all files, prints summary, saves JSON

- [ ] **Step 2: Spot-check the output**

Run: `python3 -c "
import json
with open('book_database.json') as f:
    db = json.load(f)
print(f'Entries: {len(db)}')
# Show some duplicates
dups = {k: v for k, v in db.items() if v['duplicate']}
print(f'Duplicates: {len(dups)}')
# Show entries with author populated
with_author = {k: v for k, v in db.items() if v['author']}
print(f'With author: {len(with_author)}')
# Show entries with page_count
with_pages = {k: v for k, v in db.items() if v['page_count']}
print(f'With page count: {len(with_pages)}')
" 2>&1`
Expected: stats on database quality

- [ ] **Step 3: Run incremental (second run should be fast)**

Run: `python3 build_book_db.py --db book_database.json ~/EBooks /Volumes/SuperV/EBooks 2>&1 | tail -10`
Expected: all entries processed as duplicates (~), merge step reports 0 new

- [ ] **Step 4: Commit**

```bash
git add build_book_db.py book_database.json
git commit -m "feat: initial book database build"
```
