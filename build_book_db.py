#!/usr/bin/env python3

"""
build_book_db — scans directories for book files, extracts metadata via
PyMuPDF/ebooklib/Pillow, and maintains a JSON database of books.

Usage:
    python3 build_book_db.py [directories ...] [--db PATH]

Depends on: sort_books.py (for CATEGORIES, strip_metadata, normalize_name, classify)
Optional deps: PyMuPDF (fitz), ebooklib, Pillow
"""

import argparse
import json
import os
import re
import sys

from sort_books import CATEGORIES, strip_metadata, normalize_name, classify

SUPPORTED_EXTENSIONS = {'.pdf', '.epub', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan directories for book files and build a JSON database."
    )
    parser.add_argument(
        "--db",
        default="book_database.json",
        help="Path to JSON database file",
    )
    parser.add_argument(
        "directories",
        nargs="+",
        help="One or more book directories to scan",
    )
    return parser.parse_args()


def scan_directory(root_dir):
    """Yield (filepath, ext) for every supported book file under root_dir."""
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                yield os.path.join(dirpath, fname), ext


def extract_pdf_metadata(filepath):
    """Extract metadata from a PDF using PyMuPDF."""
    import fitz
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        doc = fitz.open(filepath)
        result["page_count"] = doc.page_count
        meta = doc.metadata or {}
        result["author"] = meta.get("author") or None
        result["publisher"] = meta.get("publisher") or None
        if not result["publisher"]:
            result["publisher"] = meta.get("producer") or None
        subject = meta.get("subject", "") or ""
        isbn_match = re.search(r'(?:ISBN[:\s]*)?(\d{13}|\d{9}[\dXx])', subject)
        if isbn_match:
            result["isbn"] = isbn_match.group(1)
        if not result["isbn"]:
            fname = os.path.basename(filepath)
            isbn_match = re.search(r'(\d{13}|\d{9}[\dXx])', fname)
            if isbn_match:
                result["isbn"] = isbn_match.group(1)
        doc.close()
    except Exception as e:
        print(f"  [WARN] PDF extraction failed: {filepath} — {e}", file=sys.stderr)
    return result


def extract_epub_metadata(filepath):
    """Extract metadata from an EPUB using ebooklib."""
    import ebooklib
    from ebooklib import epub
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        book = epub.read_epub(filepath)
        creators = book.get_metadata('DC', 'creator')
        if creators:
            result["author"] = creators[0][0]
        publishers = book.get_metadata('DC', 'publisher')
        if publishers:
            result["publisher"] = publishers[0][0]
        identifiers = book.get_metadata('DC', 'identifier')
        for ident in identifiers:
            val = ident[0]
            isbn_match = re.search(r'(?:ISBN[:\s]*)?(\d{13}|\d{9}[\dXx])', val)
            if isbn_match:
                result["isbn"] = isbn_match.group(1)
                break
        spine_count = len(list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)))
        if spine_count > 0:
            result["page_count"] = spine_count
    except Exception as e:
        print(f"  [WARN] EPUB extraction failed: {filepath} — {e}", file=sys.stderr)
    return result


def extract_image_metadata(filepath):
    """Extract metadata from an image using Pillow."""
    from PIL import Image
    result = {"page_count": None, "author": None, "publisher": None, "isbn": None}
    try:
        with Image.open(filepath) as img:
            result["page_count"] = 1
    except Exception as e:
        print(f"  [WARN] Image extraction failed: {filepath} — {e}", file=sys.stderr)
    return result


def extract_author_from_filename(raw_name):
    stem = raw_name
    if '.' in stem:
        stem = stem[:stem.rfind('.')]
    stem = re.sub(r'^\d+:\s*', '', stem)

    paren_contents = re.findall(r'\(([^)]*)\)', stem)

    for content in paren_contents:
        content = content.strip()
        if re.search(
            r'z.library|libgen|pdfdrive|anna.s\s*archive|isbn|\d{4}|'
            r'edition|converted|early.release|rough.cut|meap|illustrated|guidebook',
            content, re.I
        ):
            continue
        if re.match(r'^\d+$', content):
            continue
        if re.search(r'[,&]|\b[A-Z][a-z]+\s+[A-Z][a-z]+', content):
            cleaned = re.sub(r'\s+etc\.?\s*$', '', content, flags=re.I).strip()
            if cleaned:
                return cleaned

    return None


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


def build_entry(filepath, ext):
    """Build a book database entry dict from a file."""
    fname = os.path.basename(filepath)
    raw = re.sub(r'^\d+:\s*', '', fname)

    from sort_books import extract_clean_name
    cleaned, _ = extract_clean_name(raw)
    normalized = normalize_name(cleaned)
    category = classify(normalized, raw)

    meta = extract_metadata(filepath, ext)
    file_size = os.path.getsize(filepath)

    author = meta["author"]
    if author is None:
        author = extract_author_from_filename(raw)

    return {
        "normalized_name": normalized,
        "raw_filenames": [raw],
        "author": author,
        "publisher": meta["publisher"],
        "category": category,
        "page_count": meta["page_count"],
        "isbn": meta["isbn"],
        "file_size": file_size,
        "file_path": filepath,
        "format": ext.lstrip("."),
        "last_updated": __import__('datetime').date.today().isoformat(),
        "duplicate": False,
        "notes": None,
    }


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
    Returns True if new entry, False if duplicate/merge.
    """
    key = entry["normalized_name"]
    if key in db:
        existing = db[key]
        raw = entry["raw_filenames"][0]
        if raw not in existing["raw_filenames"]:
            existing["raw_filenames"].append(raw)
        existing["duplicate"] = len(existing["raw_filenames"]) > 1
        for field in ("author", "publisher", "isbn", "notes"):
            if existing.get(field) is None and entry.get(field) is not None:
                existing[field] = entry[field]
        if existing.get("page_count") is None and entry.get("page_count") is not None:
            existing["page_count"] = entry["page_count"]
        existing["category"] = entry["category"]
        existing["file_size"] = entry["file_size"]
        existing["file_path"] = entry["file_path"]
        existing["format"] = entry["format"]
        existing["last_updated"] = entry["last_updated"]
        return False
    else:
        db[key] = entry
        return True


def save_database(db, db_path):
    """Write database to JSON file."""
    tmp_path = db_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, db_path)
    print(f"Saved {len(db)} entries to {db_path}")


def main():
    args = parse_args()

    db = load_database(args.db)
    new_count = 0
    dup_count = 0
    skip_count = 0
    total_files = 0

    for d in args.directories:
        if not os.path.isdir(d):
            print(f"Error: '{d}' is not a valid directory", file=sys.stderr)
            sys.exit(1)
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
    print(f"\n{'=' * 50}")
    print(f"  Total files scanned: {total_files}")
    print(f"  New entries:         {new_count}")
    print(f"  Duplicates merged:   {dup_count}")
    print(f"  Skipped (errors):    {skip_count}")
    print(f"  Database entries:    {len(db)}")
    print(f"{'=' * 50}")


if __name__ == '__main__':
    main()
