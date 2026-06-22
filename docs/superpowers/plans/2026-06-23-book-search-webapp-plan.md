# Book Search Webapp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Flask + HTMX SPA that searches `book_database.json` with an Anna's Archive-style interface

**Architecture:** Flask app loads JSON DB in memory, serves Jinja2 templates. HTMX handles search, filter, pagination as partial swaps. Detail page shows metadata + file actions (open in Finder, copy path, save notes).

**Tech Stack:** Flask, Jinja2, HTMX (CDN), vanilla CSS

---

### Task 1: Flask application (`search_web.py`)

**Files:**
- Create: `search_web.py`
- Reads: `book_database.json`

- [ ] **Step 1: Write the Flask app with all routes**

```python
import json
import os
import subprocess
import tempfile
import time
from urllib.parse import unquote

from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)
DB_PATH = "book_database.json"

def load_database():
    with open(DB_PATH) as f:
        return json.load(f)

db = load_database()

def get_all_categories():
    cats = {}
    for entry in db.values():
        c = entry.get("category") or "Uncategorized"
        cats[c] = cats.get(c, 0) + 1
    return dict(sorted(cats.items()))

def get_all_formats():
    fmts = {}
    for entry in db.values():
        f = entry.get("format") or "unknown"
        fmts[f] = fmts.get(f, 0) + 1
    return dict(sorted(fmts.items()))

def search_books(query, categories=None, formats=None, hide_duplicates=False, sort="relevance", page=1, per_page=20):
    query_lower = query.lower().strip() if query else ""
    results = []

    for entry in db.values():
        if hide_duplicates and entry.get("duplicate"):
            continue

        if categories:
            if (entry.get("category") or "Uncategorized") not in categories:
                continue

        if formats:
            if (entry.get("format") or "unknown") not in formats:
                continue

        if query_lower:
            name = (entry.get("normalized_name") or "").lower()
            author = (entry.get("author") or "").lower()
            isbn = entry.get("isbn") or ""
            if not (query_lower in name or query_lower in author or query_lower in isbn):
                continue

        results.append(entry)

    if sort == "title":
        results.sort(key=lambda e: (e.get("normalized_name") or "").lower())
    elif sort == "author":
        results.sort(key=lambda e: (e.get("author") or "").lower())
    elif sort == "size":
        results.sort(key=lambda e: e.get("file_size") or 0, reverse=True)
    elif sort == "pages":
        results.sort(key=lambda e: e.get("page_count") or 0, reverse=True)
    else:
        results.sort(key=lambda e: (e.get("normalized_name") or "").lower())

    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    page_results = results[start:end]

    return page_results, total

@app.route("/")
def index():
    results, total = search_books("")
    return render_template("index.html",
                         results=results,
                         total=total,
                         page=1,
                         per_page=20,
                         total_pages=max(1, (total + 19) // 20),
                         query="",
                         categories=get_all_categories(),
                         formats=get_all_formats(),
                         selected_categories=[],
                         selected_formats=[],
                         hide_duplicates=False,
                         sort="relevance")

@app.route("/search")
def search():
    query = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    sort = request.args.get("sort", "relevance")
    hide_duplicates = request.args.get("hide_duplicates") == "true"
    selected_categories = request.args.getlist("category")
    selected_formats = request.args.getlist("format")

    t0 = time.time()
    results, total = search_books(
        query=query,
        categories=selected_categories or None,
        formats=selected_formats or None,
        hide_duplicates=hide_duplicates,
        sort=sort,
        page=page
    )
    elapsed = time.time() - t0

    return render_template("index.html",
                         results=results,
                         total=total,
                         page=page,
                         per_page=20,
                         total_pages=max(1, (total + 19) // 20),
                         query=query,
                         categories=get_all_categories(),
                         formats=get_all_formats(),
                         selected_categories=selected_categories,
                         selected_formats=selected_formats,
                         hide_duplicates=hide_duplicates,
                         sort=sort,
                         elapsed=elapsed)

@app.route("/book/<path:name>")
def detail(name):
    name = unquote(name)
    entry = db.get(name)
    if not entry:
        abort(404)
    duplicates = []
    for key, e in db.items():
        if e.get("duplicate") and e.get("normalized_name") == name:
            duplicates.append(e)
    return render_template("detail.html", book=entry, duplicates=duplicates)

@app.route("/book/<path:name>/open", methods=["POST"])
def open_file(name):
    name = unquote(name)
    entry = db.get(name)
    if not entry:
        return jsonify({"ok": False, "error": "Book not found"}), 404
    file_path = entry.get("file_path", "")
    if not os.path.exists(file_path):
        return jsonify({"ok": False, "error": "File not found at path"}), 404
    subprocess.run(["open", "-R", file_path])
    return jsonify({"ok": True})

@app.route("/book/<path:name>/copy-path", methods=["POST"])
def copy_path(name):
    name = unquote(name)
    entry = db.get(name)
    if not entry:
        return jsonify({"ok": False, "error": "Book not found"}), 404
    file_path = entry.get("file_path", "")
    return jsonify({"ok": True, "path": file_path})

@app.route("/book/<path:name>/notes", methods=["POST"])
def save_notes(name):
    name = unquote(name)
    entry = db.get(name)
    if not entry:
        return jsonify({"ok": False, "error": "Book not found"}), 404
    notes = request.form.get("notes", "")
    entry["notes"] = notes
    fh, tmp = tempfile.mkstemp(dir=os.path.dirname(DB_PATH), suffix=".tmp")
    try:
        with os.fdopen(fh, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DB_PATH)
    except:
        os.unlink(tmp)
        return jsonify({"ok": False, "error": "Failed to save"}), 500
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 2: Run the app to verify it starts without import errors**

Run: `python3 -c "from search_web import app; print('OK')"`

Expected: `OK` (no import errors)

- [ ] **Step 3: Commit**

```bash
git add search_web.py
git commit -m "feat: add Flask app with search and detail routes"
```

---

### Task 2: Templates (base, index, and partials)

**Files:**
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `templates/_results.html`

- [ ] **Step 1: Write `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Book Search{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
  <script>
    document.addEventListener('htmx:afterRequest', function(evt) {
      var url = evt.detail.requestConfig.path;
      var toast = document.getElementById('toast');
      if (url && url.indexOf('/copy-path') !== -1) {
        var resp = JSON.parse(evt.detail.xhr.responseText);
        if (resp.ok) {
          navigator.clipboard.writeText(resp.path);
          toast.textContent = 'Path copied to clipboard!';
        } else {
          toast.textContent = 'Error: ' + (resp.error || 'unknown');
        }
        toast.classList.add('show');
        setTimeout(function() { toast.classList.remove('show'); }, 2000);
      }
    });
  </script>
</head>
<body>
  <div id="toast"></div>
  <header class="site-header">
    <div class="container">
      <a href="/" class="logo">📚 Book Sorter</a>
      <span class="tagline">Search {{ total }} books</span>
    </div>
  </header>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Write `templates/index.html`**

```html
{% extends "base.html" %}
{% block title %}Book Search{% endblock %}
{% block content %}
<div id="search-layout" class="search-layout">
  <aside id="sidebar" class="sidebar">
    <form hx-get="/search" hx-target="#search-layout" hx-push-url="true"
          hx-trigger="change" hx-include=".search-bar input, .sort-select" class="filters-form">
      <div class="filter-group">
        <h3>Category</h3>
        {% for cat, count in categories.items() %}
        <label class="filter-label">
          <input type="checkbox" name="category" value="{{ cat }}"
                 {% if cat in selected_categories %}checked{% endif %}>
          <span>{{ cat }}</span>
          <span class="count">{{ count }}</span>
        </label>
        {% endfor %}
      </div>

      <div class="filter-group">
        <h3>Format</h3>
        {% for fmt, count in formats.items() %}
        <label class="filter-label">
          <input type="checkbox" name="format" value="{{ fmt }}"
                 {% if fmt in selected_formats %}checked{% endif %}>
          <span>{{ fmt }}</span>
          <span class="count">{{ count }}</span>
        </label>
        {% endfor %}
      </div>

      <div class="filter-group">
        <h3>Duplicates</h3>
        <label class="filter-label">
          <input type="checkbox" name="hide_duplicates" value="true"
                 {% if hide_duplicates %}checked{% endif %}>
          <span>Hide duplicates</span>
        </label>
      </div>
    </form>
  </aside>

  <section class="main-content">
    <div class="search-bar">
      <input type="search"
             name="q"
             placeholder="Search books by title, author, ISBN..."
             value="{{ query }}"
             hx-get="/search"
             hx-target="#search-layout"
             hx-push-url="true"
             hx-trigger="keyup changed delay:300ms"
             hx-include="#sidebar form"
             autofocus>
    </div>

    <div class="results-header">
      <span class="result-count">
        {% if query %}Found {% endif %}{{ total }} result{% if total != 1 %}s{% endif %}
        {% if elapsed is defined %}({{ "%.3f"|format(elapsed) }}s){% endif %}
      </span>
      <select name="sort" class="sort-select"
              hx-get="/search"
              hx-target="#search-layout"
              hx-push-url="true"
              hx-trigger="change"
              hx-include="#sidebar form, .search-bar input">
        <option value="relevance" {% if sort == 'relevance' %}selected{% endif %}>Sort: Relevance</option>
        <option value="title" {% if sort == 'title' %}selected{% endif %}>Sort: Title A-Z</option>
        <option value="author" {% if sort == 'author' %}selected{% endif %}>Sort: Author A-Z</option>
        <option value="size" {% if sort == 'size' %}selected{% endif %}>Sort: File Size</option>
        <option value="pages" {% if sort == 'pages' %}selected{% endif %}>Sort: Page Count</option>
      </select>
    </div>

    <div id="results">
      {% include "_results.html" %}
    </div>
  </section>
</div>
{% endblock %}
```

- [ ] **Step 3: Write `templates/_results.html`**

```html
{% if results %}
<ul class="result-list">
  {% for book in results %}
  <li class="result-item" data-duplicate="{{ 'true' if book.get('duplicate') else 'false' }}">
    <a href="{{ url_for('detail', name=book.normalized_name) }}" class="result-title">
      {{ book.normalized_name | replace('.pdf', '') | replace('.epub', '') | replace('.djvu', '') }}
    </a>
    <div class="result-meta">
      {% if book.author %}
      <span class="result-author">{{ book.author }}</span>
      <span class="sep">•</span>
      {% endif %}
      <span class="format-badge format-{{ book.format or 'unknown' }}">{{ (book.format or 'unknown') | upper }}</span>
      {% if book.file_size %}
      <span class="sep">•</span>
      <span>{{ "{:,.0f}".format(book.file_size / 1024) }} KB</span>
      {% endif %}
      {% if book.page_count %}
      <span class="sep">•</span>
      <span>{{ book.page_count }} pages</span>
      {% endif %}
      {% if book.get('duplicate') %}
      <span class="dup-badge">duplicate</span>
      {% endif %}
    </div>
  </li>
  {% endfor %}
</ul>

{% if total_pages > 1 %}
<nav class="pagination" hx-target="#search-layout" hx-push-url="true"
     hx-include="#sidebar form, .search-bar input">
  {% if page > 1 %}
  <a href="#"
     hx-get="/search"
     hx-vals='{"page":{{ page - 1 }}}'
     class="page-link">‹ Prev</a>
  {% endif %}

  {% for p in range(1, total_pages + 1) %}
    {% if p == page %}
    <span class="page-link current">{{ p }}</span>
    {% elif p <= 3 or p > total_pages - 3 or (p >= page - 1 and p <= page + 1) %}
    <a href="#"
       hx-get="/search"
       hx-vals='{"page":{{ p }}}'
       class="page-link">{{ p }}</a>
    {% elif p == 4 or p == total_pages - 3 %}
    <span class="page-link dots">…</span>
    {% endif %}
  {% endfor %}

  {% if page < total_pages %}
  <a href="#"
     hx-get="/search"
     hx-vals='{"page":{{ page + 1 }}}'
     class="page-link">Next ›</a>
  {% endif %}
</nav>
{% endif %}

{% else %}
<div class="no-results">
  <p>No books found matching your query.</p>
  <p>Try different keywords or adjust your filters.</p>
</div>
{% endif %}
```

- [ ] **Step 4: Commit**

```bash
git add templates/base.html templates/index.html templates/_results.html
git commit -m "feat: add base template, search page, and results partial"
```

---

### Task 3: Detail page template

**Files:**
- Create: `templates/detail.html`

- [ ] **Step 1: Write `templates/detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ book.normalized_name }} — Book Details{% endblock %}
{% block content %}
<nav class="breadcrumb">
  <a href="/">&larr; Back to search</a>
</nav>

<div class="detail-layout">
  <div class="detail-main">
    <h1 class="detail-title">{{ book.normalized_name | replace('.pdf', '') | replace('.epub', '') | replace('.djvu', '') }}</h1>
    {% if book.author %}
    <p class="detail-author">{{ book.author }}</p>
    {% endif %}

    <table class="detail-table">
      <tr>
        <th>Category</th>
        <td>{{ book.category or '—' }}</td>
      </tr>
      <tr>
        <th>Format</th>
        <td><span class="format-badge format-{{ book.format or 'unknown' }}">{{ (book.format or 'unknown') | upper }}</span></td>
      </tr>
      <tr>
        <th>Pages</th>
        <td>{{ book.page_count or '—' }}</td>
      </tr>
      <tr>
        <th>ISBN</th>
        <td>{{ book.isbn or '—' }}</td>
      </tr>
      <tr>
        <th>Publisher</th>
        <td>{{ book.publisher or '—' }}</td>
      </tr>
      <tr>
        <th>File Size</th>
        <td>
          {% if book.file_size %}
          {{ "{:,.0f}".format(book.file_size / 1024) }} KB
          {% else %}—{% endif %}
        </td>
      </tr>
      <tr>
        <th>File Path</th>
        <td class="file-path-cell"><code>{{ book.file_path }}</code></td>
      </tr>
    </table>

    <div class="detail-actions">
      <button class="btn"
              hx-post="{{ url_for('open_file', name=book.normalized_name) }}"
              hx-swap="none"
              hx-trigger="click"
              onclick="event.preventDefault(); htmx.trigger(this, 'click');">
        📁 Open in Finder
      </button>
      <button class="btn btn-secondary"
              hx-post="{{ url_for('copy_path', name=book.normalized_name) }}"
              hx-swap="none"
              hx-trigger="click"
              onclick="event.preventDefault(); htmx.trigger(this, 'click');">
        📋 Copy Path
      </button>
    </div>

    {% if duplicates %}
    <div class="duplicates-section">
      <h3>Duplicates ({{ duplicates | length }})</h3>
      <ul class="dup-list">
        {% for dup in duplicates %}
        <li><code>{{ dup.file_path }}</code></li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    <div class="notes-section">
      <h3>Notes</h3>
      <textarea id="notes-editor" name="notes" class="notes-editor" rows="5">{{ book.notes or '' }}</textarea>
      <button class="btn btn-secondary"
              hx-post="{{ url_for('save_notes', name=book.normalized_name) }}"
              hx-include="#notes-editor"
              hx-target="#notes-status"
              hx-swap="innerHTML">
        Save Notes
      </button>
      <span id="notes-status"></span>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/detail.html
git commit -m "feat: add book detail template with metadata and actions"
```

---

### Task 4: CSS styles

**Files:**
- Create: `static/style.css`

- [ ] **Step 1: Write `static/style.css`**

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #f5f5f5;
  color: #222;
  line-height: 1.5;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
}

/* Toast */
#toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #333;
  color: #fff;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.3s;
  z-index: 999;
  pointer-events: none;
}
#toast.show {
  opacity: 1;
}

/* Header */
.site-header {
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 12px 0;
  margin-bottom: 20px;
}
.site-header .container {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.logo {
  font-size: 20px;
  font-weight: 600;
  color: #222;
  text-decoration: none;
}
.tagline {
  font-size: 13px;
  color: #777;
}

/* Layout */
.search-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

/* Sidebar */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  position: sticky;
  top: 16px;
}
.filter-group {
  margin-bottom: 20px;
}
.filter-group:last-child {
  margin-bottom: 0;
}
.filter-group h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  margin-bottom: 8px;
}
.filter-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  cursor: pointer;
  font-size: 13px;
  color: #444;
}
.filter-label:hover {
  color: #000;
}
.filter-label input[type="checkbox"] {
  accent-color: #3b82f6;
}
.filter-label .count {
  margin-left: auto;
  color: #999;
  font-size: 12px;
}

/* Main content */
.main-content {
  flex: 1;
  min-width: 0;
}

/* Search bar */
.search-bar {
  margin-bottom: 16px;
}
.search-bar input {
  width: 100%;
  padding: 12px 16px;
  font-size: 16px;
  border: 2px solid #ddd;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s;
  background: #fff;
}
.search-bar input:focus {
  border-color: #3b82f6;
}
.search-bar input::placeholder {
  color: #aaa;
}

/* Results header */
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.result-count {
  font-size: 13px;
  color: #777;
}
.sort-select {
  font-size: 13px;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  color: #555;
  cursor: pointer;
}

/* Result list */
.result-list {
  list-style: none;
}
.result-item {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 8px;
  transition: border-color 0.15s;
}
.result-item:hover {
  border-color: #bbb;
}
.result-item[data-duplicate="true"] {
  opacity: 0.65;
}
.result-title {
  font-size: 15px;
  font-weight: 500;
  color: #1a0dab;
  text-decoration: none;
  display: block;
  margin-bottom: 4px;
}
.result-title:hover {
  text-decoration: underline;
}
.result-meta {
  font-size: 13px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.result-author {
  color: #444;
}
.sep {
  color: #ccc;
}
.dup-badge {
  font-size: 11px;
  background: #fef3cd;
  color: #856404;
  padding: 1px 6px;
  border-radius: 3px;
}

/* Format badges */
.format-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.format-pdf {
  background: #fee2e2;
  color: #b91c1c;
}
.format-epub {
  background: #dcfce7;
  color: #166534;
}
.format-image {
  background: #dbeafe;
  color: #1e40af;
}
.format-unknown {
  background: #f3f4f6;
  color: #6b7280;
}

/* No results */
.no-results {
  text-align: center;
  padding: 60px 20px;
  color: #888;
}
.no-results p {
  margin-bottom: 8px;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 4px;
  margin: 20px 0;
}
.page-link {
  display: inline-block;
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid #ddd;
  border-radius: 4px;
  color: #555;
  text-decoration: none;
  background: #fff;
  cursor: pointer;
}
.page-link:hover {
  background: #f0f0f0;
}
.page-link.current {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
.page-link.dots {
  border: none;
  color: #999;
  cursor: default;
}

/* Detail page */
.breadcrumb {
  margin-bottom: 16px;
}
.breadcrumb a {
  color: #3b82f6;
  text-decoration: none;
  font-size: 14px;
}
.breadcrumb a:hover {
  text-decoration: underline;
}
.detail-layout {
  max-width: 800px;
}
.detail-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 4px;
  line-height: 1.3;
}
.detail-author {
  font-size: 16px;
  color: #666;
  margin-bottom: 20px;
}

/* Detail table */
.detail-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 20px;
}
.detail-table th,
.detail-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  font-size: 14px;
  text-align: left;
}
.detail-table th {
  width: 140px;
  color: #888;
  font-weight: 500;
}
.file-path-cell code {
  font-size: 12px;
  word-break: break-all;
  color: #666;
}

/* Action buttons */
.detail-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 14px;
  border: 1px solid #3b82f6;
  border-radius: 6px;
  background: #3b82f6;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.btn:hover {
  background: #2563eb;
}
.btn-secondary {
  background: #fff;
  color: #3b82f6;
}
.btn-secondary:hover {
  background: #f0f7ff;
}

/* Duplicates section */
.duplicates-section {
  margin-bottom: 24px;
}
.duplicates-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #555;
}
.dup-list {
  list-style: none;
}
.dup-list li {
  padding: 4px 0;
}
.dup-list code {
  font-size: 12px;
  color: #666;
  word-break: break-all;
}

/* Notes section */
.notes-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #555;
}
.notes-editor {
  width: 100%;
  padding: 10px;
  font-size: 13px;
  border: 1px solid #ddd;
  border-radius: 6px;
  resize: vertical;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.5;
  margin-bottom: 8px;
}
.notes-editor:focus {
  outline: none;
  border-color: #3b82f6;
}
#notes-status {
  font-size: 13px;
  margin-left: 8px;
  color: #166534;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add Anna's Archive-inspired CSS styles"
```

---

### Task 5: Wire up and verify

**Depends on:** Tasks 1-4

- [ ] **Step 1: Install Flask if not present**

Run: `pip3 install flask`

Expected: Flask installed

- [ ] **Step 2: Start the app and test search page**

Run: `python3 search_web.py` (in background, or separate terminal)

Expected: Server starts on `http://127.0.0.1:5000`

- [ ] **Step 3: Verify search page loads**

Run: `curl -s http://127.0.0.1:5000/ | head -20`

Expected: HTML response with search page, no errors

- [ ] **Step 4: Verify search endpoint returns partial**

Run: `curl -s 'http://127.0.0.1:5000/search?q=python' | head -20`

Expected: HTML fragment with results

- [ ] **Step 5: Verify detail page loads for a known book**

```bash
curl -s 'http://127.0.0.1:5000/book/Realizing%20Complex%20System%20Design.pdf' | head -20
```

Expected: Detail page HTML with metadata table

- [ ] **Step 6: Verify file action endpoints**

```bash
curl -s -X POST 'http://127.0.0.1:5000/book/Realizing%20Complex%20System%20Design.pdf/open'
```

Expected: `{"ok":true}` (opens Finder)

```bash
curl -s -X POST 'http://127.0.0.1:5000/book/Realizing%20Complex%20System%20Design.pdf/copy-path'
```

Expected: `{"ok":true,"path":"..."}`

- [ ] **Step 7: Verify notes save endpoint**

```bash
curl -s -X POST 'http://127.0.0.1:5000/book/Realizing%20Complex%20System%20Design.pdf/notes' \
  -d 'notes=test note'
```

Expected: `{"ok":true}`

Verify it persists: `python3 -c "import json; d=json.load(open('book_database.json')); print(d.get('Realizing Complex System Design.pdf',{}).get('notes'))"`

Expected: `test note`

- [ ] **Step 8: Verify 404 for unknown book**

```bash
curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:5000/book/nonexistent.pdf'
```

Expected: `404`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: book search webapp with Flask + HTMX"
```
