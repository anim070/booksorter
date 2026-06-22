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
    t0 = time.time()
    results, total = search_books("")
    elapsed = time.time() - t0
    return render_template("index.html",
                         elapsed=elapsed,
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
    return "Saved" if notes else "Cleared"

if __name__ == "__main__":
    app.run(debug=True)
