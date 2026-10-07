#!/usr/bin/env python3
"""
Classify books as standalone or linear, updating books.json.

Standalone books: can be opened to any page and make sense
- Philosophy (aphorisms, essays, dialogues)
- Religion (scripture, wisdom literature)
- Sectioned texts (numbered sections)
- Essays and letters

Linear books: require context, narrative flow
- Novels and stories
- History (narrative form)
- Most prose unless explicitly standalone

Usage:
    python classify_books.py           # Preview changes
    python classify_books.py --apply   # Update books.json
"""

import json
import argparse
from pathlib import Path

BOOKS_JSON = Path(__file__).parent / "books.json"

# Topics that are typically standalone (each section works alone)
STANDALONE_TOPICS = {
    "philosophy",
    "religion",
}

# Authors whose works are aphoristic/standalone by nature
STANDALONE_AUTHORS = {
    "marcus aurelius",
    "seneca",
    "epictetus",
    "lao tzu",
    "confucius",
    "montaigne",
    "emerson",
    "nietzsche",
    "pascal",
    "la rochefoucauld",
    "gracian",
    "schopenhauer",
    "bacon",
    "plutarch",
}

# Title patterns that suggest standalone content
STANDALONE_TITLE_PATTERNS = [
    "meditations",
    "essays",
    "letters",
    "pensees",
    "maxims",
    "aphorisms",
    "proverbs",
    "sayings",
    "discourses",
    "dialogues",
    "enchiridion",
    "analects",
    "tao te ching",
    "bible",
    "quran",
    "bhagavad gita",
    "upanishads",
    "dhammapada",
]


def should_be_standalone(meta: dict) -> bool:
    """
    Determine if a book should be classified as standalone.
    """
    form = meta.get("form", "prose")
    topic = meta.get("topic", "").lower()
    author = meta.get("author", "").lower()
    title = meta.get("title", "").lower()

    # Sectioned texts are always standalone
    if form == "sectioned":
        return True

    # Philosophy and religion topics are typically standalone
    if topic in STANDALONE_TOPICS:
        return True

    # Check author
    for standalone_author in STANDALONE_AUTHORS:
        if standalone_author in author:
            return True

    # Check title patterns
    for pattern in STANDALONE_TITLE_PATTERNS:
        if pattern in title:
            return True

    # Default: linear narrative (not standalone)
    return False


def main():
    parser = argparse.ArgumentParser(description="Classify books as standalone or linear")
    parser.add_argument("--apply", action="store_true", help="Actually update books.json")
    args = parser.parse_args()

    with open(BOOKS_JSON, 'r', encoding='utf-8') as f:
        books = json.load(f)

    standalone_count = 0
    linear_count = 0
    changes = []

    for gid, meta in books.items():
        is_standalone = should_be_standalone(meta)
        current = meta.get("standalone")

        if current != is_standalone:
            changes.append((gid, meta.get("title"), is_standalone))

        if is_standalone:
            standalone_count += 1
            meta["standalone"] = True
        else:
            linear_count += 1
            meta["standalone"] = False

    print(f"Classification results:")
    print(f"  Standalone: {standalone_count} books")
    print(f"  Linear: {linear_count} books")
    print()

    if changes:
        print(f"Changes ({len(changes)} books):")
        for gid, title, is_standalone in changes[:20]:
            status = "standalone" if is_standalone else "linear"
            print(f"  [{gid}] {title[:50]}: -> {status}")
        if len(changes) > 20:
            print(f"  ... and {len(changes) - 20} more")
        print()

    if args.apply:
        with open(BOOKS_JSON, 'w', encoding='utf-8') as f:
            json.dump(books, f, indent=2, ensure_ascii=False)
        print(f"Updated {BOOKS_JSON}")
    else:
        print("Dry run. Use --apply to update books.json")


if __name__ == "__main__":
    main()
