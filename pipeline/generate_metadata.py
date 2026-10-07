#!/usr/bin/env python3
"""
Generate stub metadata for books without books.json entries.
Extracts title/author from Gutenberg file headers when possible.
"""

import json
import re
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
RAW_DIR = PIPELINE_DIR / "raw"
BOOKS_JSON = PIPELINE_DIR / "books.json"

def extract_metadata_from_file(filepath: Path) -> dict:
    """Try to extract title and author from Gutenberg header."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            # Read first 3000 chars to find header
            header = f.read(3000)
    except:
        return {}

    metadata = {}

    # Common Gutenberg header patterns
    # Title: X
    title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', header, re.IGNORECASE)
    if title_match:
        metadata['title'] = title_match.group(1).strip()

    # Author: X
    author_match = re.search(r'Author:\s*(.+?)(?:\n|$)', header, re.IGNORECASE)
    if author_match:
        metadata['author'] = author_match.group(1).strip()

    # Release Date for era estimation
    date_match = re.search(r'Release Date:\s*.*?(\d{4})', header, re.IGNORECASE)
    # This is release date, not publication date - not useful

    # Language
    lang_match = re.search(r'Language:\s*(.+?)(?:\n|$)', header, re.IGNORECASE)
    if lang_match:
        lang = lang_match.group(1).strip().lower()
        if lang != 'english':
            metadata['language'] = lang

    return metadata

def main():
    print("Generating metadata for new books")
    print("=" * 50)

    # Load existing metadata
    with open(BOOKS_JSON, 'r', encoding='utf-8') as f:
        books_meta = json.load(f)

    print(f"Existing entries: {len(books_meta)}")

    # Find all raw files
    raw_files = list(RAW_DIR.glob("pg*.txt"))
    print(f"Books in raw/: {len(raw_files)}")

    added = 0
    skipped_non_english = 0

    for filepath in sorted(raw_files, key=lambda x: int(re.search(r'(\d+)', x.name).group(1))):
        match = re.match(r'pg(\d+)\.txt', filepath.name)
        if not match:
            continue

        gid = match.group(1)

        if gid in books_meta:
            continue

        # Extract metadata from file
        extracted = extract_metadata_from_file(filepath)

        # Skip non-English books
        if extracted.get('language') and extracted['language'] != 'english':
            skipped_non_english += 1
            continue

        # Create entry with defaults
        entry = {
            "title": extracted.get('title', f"Gutenberg #{gid}"),
            "author": extracted.get('author', "Unknown"),
            "era": "unknown",
            "topic": "literature",  # Default topic
            "form": "prose",
            "description": ""
        }

        books_meta[gid] = entry
        added += 1

        if added <= 10 or added % 200 == 0:
            print(f"  Added: {entry['title'][:50]} by {entry['author'][:30]}")

    print(f"\nAdded {added} new entries, skipped {skipped_non_english} non-English")
    print(f"Total entries: {len(books_meta)}")

    # Write updated metadata
    with open(BOOKS_JSON, 'w', encoding='utf-8') as f:
        json.dump(books_meta, f, indent=2, ensure_ascii=False)

    print(f"Updated {BOOKS_JSON}")

if __name__ == "__main__":
    main()
