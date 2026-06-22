# Book Search Webapp — Design Spec

## Overview

A local SPA-like webapp that searches the `book_database.json` and presents results in an Anna's Archive-style interface. Built with Flask + HTMX — no JS framework, zero build step.

## Backend

**Stack:** Flask, Jinja2, HTMX (client-side library loaded from CDN)

**Entry point:** `search_web.py` — run with `python3 search_web.py`, binds to `http://localhost:5000`

**Data:** Loads `book_database.json` into memory at startup (~3.5K entries, ~6MB). All search and filter operations run in-process.

### Routes

| Method | Route | Returns | Purpose |
|--------|-------|---------|---------|
| GET | `/` | Full page | Search page with initial results |
| GET | `/search` | HTMX partials | `_results.html` + `_sidebar.html` fragments |
| GET | `/book/<normalized_name>` | Full page | Book detail page |
| POST | `/book/<normalized_name>/open` | JSON | Opens file in Finder (`open -R`) |
| POST | `/book/<normalized_name>/copy-path` | JSON | Returns file path for clipboard |
| POST | `/book/<normalized_name>/notes` | JSON | Saves notes field back to JSON DB |

### Search Logic

- Case-insensitive substring match against `normalized_name`, `author`, `isbn`
- Sidebar filters: `category` (multi-select), `format` (PDF/EPUB/image), `duplicate` toggle
- Sort options: relevance (default), title A-Z, author A-Z, file size, page count
- Pagination: 20 results per page, HTMX handles page load via `hx-target`
- Response includes result count and search time in ms

### File Actions

- **Open in Finder:** `subprocess.run(["open", "-R", file_path])` — macOS only
- **Copy Path:** Returns the file path in JSON response; user copies via HTMX-triggered clipboard API on the client side
- Both actions gracefully handle missing files

### Notes Editing

- Notes field is loaded from `book_database.json` on detail page
- Editable textarea, save button sends POST with new notes content
- Backend updates the in-memory dict and writes the full JSON back atomically (tempfile + replace, same pattern as `build_book_db.py`)
- `notes` field is never overwritten by `build_book_db.py` — this preserves manual edits

## Frontend

### Template structure

```
templates/
  base.html        — HTML shell: head, nav bar, body, HTMX CDN
  index.html       — search page: sidebar + search bar + results area
  detail.html      — book detail page
  _sidebar.html    — filter sidebar partial
  _results.html    — result list rows partial
static/
  style.css        — all styles
```

### Search Page Layout

```
+-----+----------------------------------------------------+
|  F  |  Anna's Archive-style logo/brand                    |
|  I  |  ┌──────────────────────────────────────────────┐  |
|  L  |  │  🔍 Search books by title, author, ISBN...  │  |
|  T  |  └──────────────────────────────────────────────┘  |
|  E  |                                                     |
|  R  |  Showing 20 of 3,547 results (0.004s)              |
|  S  |                                                     |
|     |  📄 Book Title                             5.2 MB  |
|  C  |      Author Name               PDF  |  Category   |
|  A  |  ─────────────────────────────────────────────────  |
|  T  |  📄 Another Title                      1.8 MB       |
|  E  |      Author Name              EPUB  |  Category   |
|  G  |  ─────────────────────────────────────────────────  |
|  O  |  ...                                                |
|  R  |  < 1 2 3 4 5 ... >                                  |
|  Y  |                                                     |
+-----+----------------------------------------------------+
```

### Detail Page Layout

```
+----------------------------------------------------+
│  ← Back to results                                  │
+----------------------------------------------------+
│  # Book Title                                       │
│  Author Name                                        │
│                                                     │
│  ┌──────────────┬──────────────────────────────┐   │
│  │  Category     │  Programming / Software Eng │   │
│  │  Format       │  PDF                        │   │
│  │  Pages        │  521                        │   │
│  │  ISBN         │  978-0-123-45678-9          │   │
│  │  Publisher    │  O'Reilly Media             │   │
│  │  File Size    │  9.2 MB                     │   │
│  │  File Path    │  /Volumes/.../book.pdf      │   │
│  └──────────────┴──────────────────────────────┘   │
│                                                     │
│  [📁 Open in Finder]  [📋 Copy Path]                │
│                                                     │
│  Duplicates (2):                                    │
│  ── /path/to/copy1.pdf                              │
│  ── /path/to/copy2.pdf                              │
│                                                     │
│  Notes:                                             │
│  ┌──────────────────────────────────────────────┐   │
│  │ [textarea]                                   │   │
│  └──────────────────────────────────────────────┘   │
│  [Save Notes]                                       │
+----------------------------------------------------+
```

### Styling

Anna's Archive-inspired clean, minimal aesthetic:
- White/light gray background, dark text
- Monospace-ish or system font stack
- Subtle borders and shadows on cards
- Blue accent color for links and buttons
- Format badges (PDF=red, EPUB=green, image=blue)
- No flashy elements — functional, readable, fast

### HTMX Interactions

- **Search:** `hx-trigger="keyup changed delay:300ms"` on search input → `GET /search`
  - Target: `#results` and `#sidebar` swap
  - Push URL: `history.pushUrl=true` so browser back works
- **Pagination:** `hx-get="/search?q=...&page=2"` on page links → swap `#results`
- **Filters:** `hx-get="/search?q=...&category=...&format=..."` on checkbox/select change
- **Open in Finder:** `hx-post` → swap with toast notification on success/error
- **Copy Path:** `hx-post` → client-side JS copies returned path to clipboard
- **Save Notes:** `hx-post` → swap with success indicator

## Error Handling

- **No results:** Show "No books found matching your query" with illustration
- **Missing file:** Open/Copy actions show "File not found at path" toast
- **Invalid book name in detail URL:** 404 page with link back to search
- **JSON save failure:** Error message shown inline near the notes field

## Non-Goals

- No authentication (local tool)
- No download functionality (local files)
- No bulk operations
- No real-time sync

## Files to Create

```
search_web.py              — Flask app (~150 lines)
templates/base.html        — base template (~30 lines)
templates/index.html       — search page (~40 lines)
templates/detail.html      — detail page (~60 lines)
templates/_results.html    — result rows partial (~30 lines)
templates/_sidebar.html    — filter sidebar partial (~20 lines)
static/style.css           — all styles (~200 lines)
```

## Platform Notes

- **Open in Finder:** macOS only, uses `open -R`. On Linux, `xdg-open` fallback; on Windows, `explorer /select,"`. Currently scoped to macOS only.
- **Book names in URLs:** URL-encoded with `quote()` since filenames contain spaces, parens, dots. Decoded with `unquote()` on the server side.
```

## Dependencies

- `flask` (pip install)
