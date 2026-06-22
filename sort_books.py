"""
Booksorter — reads book filenames from input lists, strips download-site
metadata (z-library, Anna's Archive, ISBNs, libgen, PDFDrive, etc.), and
groups books into categories via keyword matching.

Usage:
    python3 sort_books.py [file1 file2 ...]

    If no files are given, defaults to book_list.txt and book_list_2.txt.

Input:
    Each line is a filename; lines starting with "N:" are stripped of the
    prefix. Blank lines are skipped.

Output:
    Prints categorized groups to stdout, one section per category with
    a book count header. Each cleaned name is shown; if it differs from
    the original, the original is shown below on an indented "(was:)"
    line. A total count is printed at the end.

Categories:
    Defined in CATEGORIES (a list of dicts). Each category has a name
    and a list of regex keyword patterns. Bengali Books are detected by
    Unicode range check on the raw filename. The first matching category
    wins; unmatched books fall into "Miscellaneous".

Metadata stripped:
    - Download site markers: z-library.sk, Z-Library, Anna's Archive
    - Author/publisher info in parentheses
    - Early release / MEAP / Rough Cut labels
    - ISBNs, DOI refs, ISBN13 hashes
    - libgen.li, PDFDrive, fdmdownload suffixes
    - HTML entities, leading hex hashes, leading underscores
    - Year brackets [2015], trailing duplicate markers (1)
    - Em dashes, underscores, and assorted separators

No dependencies — pure Python stdlib only.
"""

import os
import re
import sys

CATEGORIES = [
    {
        "name": "Bengali Books",
        "keywords": [],
        "detect_bengali": True,
    },
    {
        "name": "Trains / Locomotives",
        "keywords": [
            r"\btrains?\b", "locomotive", "passenger.*train",
        ],
    },
    {
        "name": "Privacy / Anonymity",
        "keywords": [
            "extreme privacy", "bazzell", "how to disappear",
            "linux device", "macos device", "mobile device",
        ],
    },
    {
        "name": "Military / Warfare / Weapons",
        "keywords": [
            "military", "weapon", "army", "naval",
            "missile", "artillery", r"\btank\b", "combat",
            "aircraft", "fighter", "bomber",
            r"\bgun\b", "firearm", "ammunition", "ballistic",
            "explosive", "propellent", "flintlock", "muskets",
            "AFV", "carrier killer", "hybrid warfare",
            "information warfare", "battle", "ballistics",
            "ancient weapons of oman", "german field artillery",
            "german tanks", "chinese tank", "postwar artillery",
            "firearms.*illustrated", "firearms of the british",
            "gun digest", "exploded gun",
            "history of strategic air", "history of warfare",
            "rockets and people", "from polaris to trident",
            "sea combat", "modern.*military.*aircraft",
            "russia.*warplane", "modern.*tanks",
            "strategic technologies.*military",
            "the ai military race", "ai.*military.*tech",
            "disruptive technologies.*militar",
            "military transformation", "military and related terms",
            "100 deadly skill", "castles, battles",
            "contemporary military",
            "drone.*war(?!ren)", "the drone age", "the remote revolution",
            "outsourcing war", "russian.?ukrainian war",
            "scientific way of warfare",
            "geeks of war",
            "a technical history of americas nuclear",
            "strategic.*military", "strategic.*defense",
            "strategic.*air", "military.*strategic",
            "tactical.*military", "defense.*military",
            "weapons systems", "u\\.s\\. army",
            "air.*force", "naval.*war",
        ],
    },
    {
        "name": "Physics / Mathematics",
        "keywords": [
            "physics", "mathematics", "math", "geometry",
            "algebra", "calculus", "thermodynamics", "quantum",
            "feynman", "mathematical", "trigonometry",
            "kaleidoscope", "labyrinth",
            "geometric gems", "geometry in our",
            "math puzzle", "fractionalization of particles",
            "enigma of the crookes",
            "information theory",
            "mit 8.01", "mit 8.03",
            "the flying circus of physics",
            "manga guide.*linear algebra",
            "manga guide.*electricity",
            "manga guide.*microprocessor",
            "mathematics of games and puzzles",
            "thermodynamics four laws",
        ],
    },
    {
        "name": "Space / Aerospace",
        "keywords": [
            "space", "NASA", "Apollo", "Gemini", "rocket",
            "satellite", "astronaut", "aerospace",
            "x-vehicle", "fly.?by.?wire", "digital fly",
            "ballistic missile defense",
            "digital apollo", "project apollo",
            "failure is not an option",
            "moonwalking with einstein",
        ],
    },
    {
        "name": "Medicine / Biology / Bio sciences",
        "keywords": [
            "anatomy", "genetics", "biomedical",
            "DNA", "gene", "cell", "brain", "neuroscience",
            "collagen", "biography of the pixel",
            "anatomy 101", "genetics 101",
            "biomedical engineering design",
            "materials for biomedical",
            "instrumentation handbook.*biomedical",
            "breaking boundaries",
            "we are electric",
            "spark of life",
        ],
    },
    {
        "name": "History / Social Sciences / Politics",
        "keywords": [
            "history of", "ancient", "medieval",
            "civilization", "economics?", "empire",
            "persian gulf", "trade and traders",
            "national geographic.*history",
            "100 mistakes that changed",
            "economic history",
            "encyclopedia of the exquisite",
            "the dictators handbook",
            "dictator",
        ],
    },
    {
        "name": "Business / Entrepreneurship / Product",
        "keywords": [
            "business", "startup", "entrepreneur", "marketing",
            "product.?mind", "strategy", "leadership",
            "cofounder", "dogfight become cat",
            "the entrepreneur.*tool",
            "snapchat.*deck",
            "reddit.*deck",
        ],
    },
    {
        "name": "Crafts / DIY / Bushcraft / Survival / Food",
        "keywords": [
            "bushcraft", "survival", "cooking", "food.*ancestor",
            "herb", "trapping", "gathering", "khazana",
            "tree book", "herb book",
            "baking", "recipe",
            "dye.*cotton",
        ],
    },
    {
        "name": "Electronics / Robotics / Drones",
        "keywords": [
            "electronics", "circuit", "sensor", "motor",
            "robot", "drone", "UAV", "embedded",
            "FPGA", "signal processing", "actuator",
            "arduino", "ESP32", "LoRa", "LoRaWAN",
            "transducer", "electric motor",
            "ardupilot", "pixhawk", "multicopter",
            "software.?defined radio",
            "flexible.*sensor", "smart sensor",
            "sensors and circuit",
            "handbook of multisensor",
            "array signal",
            "measurement, instrumentation",
            "design.*embedded image processing",
            "designing electronics",
            "logic synthesis.*fpga",
            "molecular aspects of bioelectricity",
            "body electric",
            "systems for printed flexible",
            "biomedical engineering.*handbook",
            "comprehensive review.*electronics",
            "electric motors and mechanical",
            "electronics for scientists",
            "bioimpedance",
            "handbook on array",
            "whitfields electrical",
        ],
    },
    {
        "name": "Engineering / Manufacturing",
        "keywords": [
            "engineering", "manufacturing", "invention",
            "how things are made", "mechanical invention",
            "inverse engineering",
            "engineering in plain sight",
            "building platforms that scale",
            "vibe engineering",
            "standard handbook for telescope",
            "building.*scale model",
        ],
    },
    {
        "name": "Communication / Telecommunications",
        "keywords": [
            "telecommunication", "data communication",
            "radar technology",
        ],
    },
    {
        "name": "Productivity / Self-Help / Learning",
        "keywords": [
            "atomic note.?tak",
            "smart note",
            "zettelkasten",
            "master obsidian",
            "becoming sherlock",
            "mastermind.*sherlock",
            "memory palace",
            "how to think like",
            "art of noticing",
            "slow looking",
            "visual intelligence",
            "look.*practical guide.*observation",
        ],
    },
    {
        "name": "Cybersecurity / Hacking / OSINT",
        "keywords": [
            "hack", "cyber", "OSINT", "threat", "vulnerability",
            "penetration", "nmap", "red team", "blue team",
            "exploit", "bug bounty", "firewall", "malware",
            "ransomware", "stuxnet", "sunburst",
            "cryptography",
            "open source intelligence",
            "anonymity",
            "purple team", "zero trust", "devsecops",
            "hacker", "cybervetting",
            "hacklog",
            "inside cyber",
            "defining second generation",
            "deep dive.*open source",
            "hack the world", "hacking gps",
            "weapons systems annual assessment",
            "policy as code",
            "web hacking",
            "operator handbook",
            "security as code", "security chaos",
            "building a cyber risk",
            "cybersecurity blue team",
            "cybersecurity myths",
            "cyber warfare documentary",
            "we are bellingcat",
            "the threat hunter",
            "the art of cyber warfare",
            "penetration testing courseware",
            "become isc2 certified",
            "beyond the algorithm ai.*security",
            "grokking web application security",
            "sans 560",
        ],
    },
    {
        "name": "AI / Machine Learning / Data Science",
        "keywords": [
            r"\bAI\b", "machine learning", "deep learning",
            "neural network", "LLM", "GPT", "transformer",
            "natural language", "NLP", "data science", "ML ops",
            "RAG", "agentic", "AI agent", "prompt engineering",
            "genAI", "generative AI", "langchain", "langraph",
            "DSPy", "RLHF", "fine.?tun", "small language model",
            "large language model", "model context protocol",
            "deepseek", "conformal prediction",
            "black box model", "machine learning platform",
            "designing multi.?agent",
            "practical guide to building agents",
            "grokking bayes", "grokking ai",
            "supervised machine learning",
            "personalized machine learning",
            "reinforcement learning", "foundation model",
            "time series forecasting",
            "context engineering",
            "build a deepseek",
            "build an ai agent", "build an llm",
            "hands.?on rag",
            "domain.?specific small language",
            "ai with intention",
            "ai.?powered pedagogy",
            "ai, automation, and war",
            "data engineering design patterns",
            "learn ai data engineering",
            "30 agents every ai engineer",
            "ai at the edge",
            "the prompt engineer",
            "organic prompting",
            "how to write ai image",
            "ai prompt engineering",
            "developers guide to ai",
            "developer.s guide to ai",
        ],
    },
    {
        "name": "Games / Game Development",
        "keywords": [
            "game console", "dune", "narrative mechanic",
            "pixel art for game",
            "how to make a video game",
            "retro game dev",
        ],
    },
    {
        "name": "Programming / Software Engineering",
        "keywords": [
            "python", "javascript", "typescript", "react",
            "angular", "CSS", "html",
            "software engineer",
            "algorithm", "data structure",
            "system design",
            "testing", "devops",
            "programming",
            "ECMAScript", "jQuery", "JSON",
            "awk programming", "tmux",
            "vim", "emacs", "markdown",
            "containers work",
            "micro.?frontend", "design pattern",
            "code review",
            "web development",
            "game engine",
            "scratch 3",
            "c\\+\\+",
            "coding interview",
            "haskell",
            "rust for embedded",
            "smaller c",
            "learning c with",
            "pixel art for game",
            "efficient linux", "learning modern linux",
            "python work", "python quiz", "python practice",
            "python for math",
            "pro html5",
            "head first javascript",
            "painless vim",
            "mastering emacs",
            "mastering design pattern",
            "mastering test.?driven",
            "specification by example",
            "automate the boring",
            "data visualization with",
            "dask.*definitive guide",
            "hypermodern python",
            "server.?side webassembly",
            "image processing in python",
            "symbolic mathematics with python",
            "applied math with python",
            "modeling and simulation in python",
            "blueprints for text analytics",
            "the coder cafe",
            "practical python",
            "powerShell", "power shell",
            "bash",
            "sql",
            "git",
            "docker",
            "k8s", "kubernetes",
            "modeling mindsets",
            "time complexity analysis",
            "problems on array",
            "mike and phanis",
            "relevant search",
            "the awk programming",
            "system firmware",
            "systems programming with zig",
            "realizing complex system",
            "effective python",
            "fluent python",
            "clean code",
            "refactoring",
            "designing data.?intensive",
            "the pragmatic programmer",
            "site reliability engineering",
            "looks good to me",
            "total typescript",
            "ultimate typescript",
            "ultimate react testing",
            "ultimate modern jquery",
            "modern web development with angular",
            "understanding ecmascript",
            "make your own pixel art",
            "html5 game development",
            "build your own 2d",
            "build an html5",
            "make your own scratch",
            "every layout",
            "master the skill of debugging css",
            "learning markdown",
            "digital twins in action",
            "dynamic authorization",
            "hands-on small language",
            "ensemble methods",
        ],
    },
    {
        "name": "Miscellaneous",
        "keywords": [],
    },
]


def has_bengali(text):
    for ch in text:
        if '\u0980' <= ch <= '\u09FF':
            return True
    return False


def strip_metadata(name):
    name = re.sub(
        r'\s*\(z-library\.sk,\s*1lib\.sk,\s*z-lib\.sk\)', '', name, flags=re.I
    )
    name = re.sub(r'\s*\(Z-Library\)', '', name, flags=re.I)
    name = re.sub(r"\s*--\s*Anna's Archive.*$", '', name, flags=re.I)

    name = re.sub(
        r"\s*--\s*(?:.+?)--\s*(?:\d{4}|\w+\s+\d{4})?\s*--\s*.+?(?:--\s*\d{13})?\s*--\s*\w{32}\s*--\s*Anna.s Archive",
        '', name, flags=re.I
    )
    name = re.sub(
        r"\s*--\s*(?:.+?)--\s*(?:\d{4})?\s*--\s*.+?(?:--\s*(?:\d{13}|\w{32}))?(?:\s*--\s*\w{32})?\s*--\s*Anna.s Archive",
        '', name, flags=re.I
    )
    name = re.sub(
        r"\s*--\s*(?:.+?)--\s*(?:\d{4})?\s*--\s*.+?(?:--.*?)?$",
        '', name, flags=re.I
    )
    name = re.sub(
        r"\s*--\s*(?:.+?)--\s*(?:isbn13\s+\S+\s*)?--\s*\w{32}\s*--\s*Anna.s Archive",
        '', name, flags=re.I
    )
    name = re.sub(
        r"\s*--\s*(?:.+?)--\s*\d{13}\s*--\s*\w{32}\s*--\s*Anna.s Archive",
        '', name, flags=re.I
    )
    name = re.sub(
        r"\s*--\s*(?:.+?),\s*\d{4}\s*--\s*.+?(?:\s*--\s*\d{13})?\s*--\s*\w{32}\s*--\s*Anna.s Archive",
        '', name, flags=re.I
    )

    name = re.sub(r'\s*\(for\s+Raymond Rhine\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(for\s+[^()]*\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(converted from EPUB\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(Good Converted\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(for\s+True Epub\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(MEAP[^)]*\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(First Early Release\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(Rough Cut\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(Early Release\s*\d*\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(Third Early Release\)', '', name, flags=re.I)

    name = re.sub(r'_?\d{4}_\d{13}_\d*\s*', '', name)
    name = re.sub(r'_?\d{4}_\d{13}_\S+\s*', '', name)
    name = re.sub(r'\d{4}_\d{13}\s*', '', name)

    name = re.sub(r'\s*_+[\s_]*_+\s*', ' ', name)
    name = re.sub(r'\s*—+\s*', ' ', name)
    name = re.sub(r'\s*–+\s*', ' ', name)
    name = re.sub(r'\s*ISBN\s+\S+\s*', '', name, flags=re.I)
    name = re.sub(r'\s*isbn13\s+\S+\s*', '', name, flags=re.I)
    name = re.sub(r'\((?:2nd|3rd|4th|5th|6th)\s+ed[^)]*\)', '', name, flags=re.I)
    name = re.sub(r'\((?:2nd|3rd|4th|5th|6th)\s+Edition[^)]*\)', '', name, flags=re.I)
    name = re.sub(r'\s*,\s*(?:2nd|3rd|4th|5th|6th)\s+Edition', '', name, flags=re.I)
    name = re.sub(r'\s*\(Illustrated\)', '', name, flags=re.I)
    name = re.sub(r'\s*\(Course\s+Guidebook\)', '', name, flags=re.I)

    name = re.sub(r'#[xX][0-9a-fA-F]{2,4};', '', name)
    name = re.sub(r'^[0-9a-f]{8,}_+', '', name)
    name = re.sub(r'^_+', '', name)
    name = re.sub(r'\s*\[EARLY RELEASE\]', '', name, flags=re.I)
    name = re.sub(r'\s*-\s*libgen\.li', '', name, flags=re.I)
    name = re.sub(r'\s*\[10\.\d+[^\]]*\]', '', name)
    name = re.sub(r'\s*-\s*PDFDrive', '', name, flags=re.I)
    name = re.sub(r'\.fdmdownload$', '', name)
    name = re.sub(r'\s*\[\d{4}\]', '', name)

    name = re.sub(r'\s*\(converted\)', '', name, flags=re.I)
    name = re.sub(r'\s*—\s*converted', '', name, flags=re.I)
    name = re.sub(r'\s*—\s*\d+', ' ', name)
    name = re.sub(r'\([^)]*\)\s*\d{4}', '', name)
    name = re.sub(r'\b\d{13}\b', '', name)
    name = re.sub(r'\b[0-9a-f]{32}\b', '', name)
    name = re.sub(r'\b[0-9a-f]{40}\b', '', name)
    name = re.sub(r'\([^)]*etc\.\)', '', name, flags=re.I)

    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\s*\(\s*\)', '', name)
    name = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', name)
    name = re.sub(r'_[a-f0-9]{6,}\s*', '', name)
    name = re.sub(r'\d{4}_', '', name)
    name = re.sub(r'_\d{4}\b', '', name)
    name = re.sub(r'\(\s*$', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip(' ,.;:-_—')
    return name


def extract_clean_name(raw_name):
    stem = raw_name
    stem = re.sub(r'\.fdmdownload$', '', stem)
    ext = stem[stem.rfind('.'):] if '.' in stem else ''
    stem = stem[:stem.rfind('.')] if '.' in stem else stem

    clean = strip_metadata(stem)
    clean = clean.strip(' .\t')
    title = clean if clean else stem
    title = re.sub(r'^\d+\.\s*', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'\(\s*', '(', title)
    title = re.sub(r'\s*\)', ')', title)
    title = re.sub(r'\(\)', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title + ext, raw_name


def classify(clean_name, raw_name):
    combined = clean_name + ' ' + raw_name

    if has_bengali(raw_name):
        return "Bengali Books"

    for cat in CATEGORIES:
        if cat["name"] == "Miscellaneous":
            continue
        for kw in cat["keywords"]:
            if re.search(kw, combined, re.I):
                return cat["name"]

    return "Miscellaneous"


def normalize_name(clean_name):
    name, ext = os.path.splitext(clean_name)
    name = re.sub(r'\s*\([^)]*\)', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip(' ,.;:-')
    return (name or os.path.splitext(clean_name)[0]) + ext


def read_book_lines(filepaths):
    lines = []
    for filepath in filepaths:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                lines.append(line)
    return lines


def main():
    filepaths = sys.argv[1:] if len(sys.argv) > 1 else ["book_list.txt", "book_list_2.txt"]
    lines = read_book_lines(filepaths)

    categorized = {cat["name"]: [] for cat in CATEGORIES}

    for line in lines:
        m = re.match(r'^\d+:\s*(.*)', line)
        raw = m.group(1) if m else line
        cleaned, _ = extract_clean_name(raw)
        cat = classify(cleaned, raw)
        normalized = normalize_name(cleaned)
        categorized[cat].append((normalized, raw))

    for cat_name, books in categorized.items():
        if not books:
            continue
        print(f"\n{'='*70}")
        print(f"  {cat_name} ({len(books)} books)")
        print(f"{'='*70}")
        for normalized, raw in sorted(books, key=lambda x: x[0].lower()):
            print(f"  {normalized}")
            if normalized != raw:
                print(f"    (was: {raw})")

    print(f"\n{'='*70}")
    total = sum(len(v) for v in categorized.values())
    print(f"  TOTAL: {total} books")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
