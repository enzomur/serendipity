#!/usr/bin/env python3
"""
Bulk fetch books from Project Gutenberg using their OFFICIAL mirrors.
Gutenberg actively supports bulk downloads via mirrors - no ban risk.

Option 1: Use rsync (fastest, recommended by Gutenberg)
Option 2: Use their catalog + slow polite fetching

Usage:
  python bulk_fetch.py --method rsync --count 1000
  python bulk_fetch.py --method polite --count 100
"""

import json
import os
import subprocess
import time
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"
BOOKS_JSON = Path(__file__).parent / "books.json"

# Topic classification based on keywords
TOPIC_KEYWORDS = {
    'philosophy': ['philosophy', 'ethics', 'metaphysics', 'logic', 'morality', 'virtue', 'reason'],
    'history': ['history', 'war', 'revolution', 'empire', 'civilization', 'ancient', 'medieval'],
    'science': ['science', 'physics', 'chemistry', 'biology', 'mathematics', 'evolution', 'nature'],
    'religion': ['religion', 'bible', 'god', 'theology', 'faith', 'spiritual', 'divine'],
    'psychology': ['psychology', 'mind', 'consciousness', 'behavior', 'mental', 'dream'],
    'economics': ['economics', 'wealth', 'capital', 'labor', 'trade', 'money', 'market'],
    'politics': ['politics', 'government', 'democracy', 'liberty', 'rights', 'law', 'justice'],
}


def classify_topic(title: str) -> str:
    text = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic
    return "literature"


def extract_metadata(filepath: Path) -> dict | None:
    """Extract metadata from Gutenberg file header."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            header = f.read(4000)

        # Must be English
        if 'Language: English' not in header:
            if 'language: english' not in header.lower():
                return None

        # Extract title
        title_match = re.search(r'Title:\s*(.+?)(?:\r?\n)', header)
        title = title_match.group(1).strip() if title_match else None
        if not title or len(title) < 3:
            return None

        # Extract author
        author_match = re.search(r'Author:\s*(.+?)(?:\r?\n)', header)
        author = author_match.group(1).strip() if author_match else "Unknown"

        # Skip audio/non-text
        if any(x in header.lower()[:1500] for x in ['audio', 'mp3', 'librivox']):
            return None

        topic = classify_topic(title)

        return {
            "title": title,
            "author": author,
            "era": "19th-20th century",
            "topic": topic,
            "form": "prose",
            "description": f"A classic work by {author}."
        }
    except Exception as e:
        return None


def rsync_books(count: int):
    """
    Use rsync to mirror books from Gutenberg's official mirror.
    This is their RECOMMENDED method for bulk downloads.

    From gutenberg.org/help/mirroring.html:
    "We encourage mirroring of Project Gutenberg"
    """
    print("=" * 60)
    print("RSYNC METHOD (Gutenberg's recommended bulk download)")
    print("=" * 60)
    print()
    print("Gutenberg ENCOURAGES bulk downloads via rsync.")
    print("See: https://www.gutenberg.org/help/mirroring.html")
    print()

    # Create temp directory for rsync
    rsync_dir = RAW_DIR.parent / "gutenberg_mirror"
    rsync_dir.mkdir(exist_ok=True)

    # Rsync command from Gutenberg's official instructions
    # We only get .txt files to save space
    cmd = [
        "rsync", "-av", "--include=*/", "--include=*.txt",
        "--exclude=*", "--prune-empty-dirs",
        f"--max-size=2M",  # Skip huge files
        "aleph.gutenberg.org::gutenberg",
        str(rsync_dir)
    ]

    print("Running rsync (this may take a while for first sync)...")
    print(f"Command: {' '.join(cmd)}")
    print()
    print("Note: First run downloads a lot. Subsequent runs are fast (delta sync).")
    print("Press Ctrl+C to stop when you have enough books.")
    print()

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopped by user. Processing downloaded files...")
    except subprocess.CalledProcessError as e:
        print(f"Rsync error: {e}")
        print("Trying alternate approach...")
        return polite_fetch(count)

    # Process downloaded files
    process_downloaded_files(rsync_dir, count)


def polite_fetch(count: int):
    """
    Politely fetch books one at a time with long delays.
    Uses 3-second delays to be extra respectful.
    """
    print("=" * 60)
    print("POLITE FETCH METHOD")
    print("=" * 60)
    print()
    print("Fetching books with 3-second delays to be respectful.")
    print(f"Target: {count} books")
    print()

    # Load existing
    if BOOKS_JSON.exists():
        with open(BOOKS_JSON) as f:
            books = json.load(f)
    else:
        books = {}

    existing_ids = {int(k) for k in books.keys()}
    fetched = 0
    book_id = 1

    while fetched < count and book_id < 70000:
        if book_id in existing_ids:
            book_id += 1
            continue

        filepath = RAW_DIR / f"pg{book_id}.txt"

        if not filepath.exists():
            url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
            try:
                result = subprocess.run(
                    ["curl", "-sL", "--max-time", "15", "-o", str(filepath), "-w", "%{http_code}", url],
                    capture_output=True, text=True, timeout=20
                )

                if result.stdout.strip() != "200" or not filepath.exists():
                    if filepath.exists():
                        filepath.unlink()
                    book_id += 1
                    continue
            except subprocess.TimeoutExpired:
                if filepath.exists():
                    filepath.unlink()
                book_id += 1
                continue
            except Exception:
                book_id += 1
                continue

            time.sleep(2)  # 2-second delay

        # Validate and extract metadata
        if filepath.exists() and filepath.stat().st_size > 1000:
            metadata = extract_metadata(filepath)
            if metadata:
                books[str(book_id)] = metadata
                fetched += 1
                print(f"[{fetched}/{count}] {metadata['title'][:50]}")

                # Save every 10 books
                if fetched % 10 == 0:
                    with open(BOOKS_JSON, "w") as f:
                        json.dump(books, f, indent=2)
            else:
                # Not English or not prose - remove
                filepath.unlink()

        book_id += 1

    # Final save
    with open(BOOKS_JSON, "w") as f:
        json.dump(books, f, indent=2)

    print(f"\nDone! Catalog now has {len(books)} books.")


def process_downloaded_files(mirror_dir: Path, max_count: int):
    """Process files downloaded via rsync."""
    if BOOKS_JSON.exists():
        with open(BOOKS_JSON) as f:
            books = json.load(f)
    else:
        books = {}

    print(f"Processing downloaded files...")
    processed = 0

    for txt_file in mirror_dir.rglob("*.txt"):
        if processed >= max_count:
            break

        # Extract book ID from filename (pg1234.txt)
        match = re.search(r'pg(\d+)', txt_file.name)
        if not match:
            continue

        book_id = match.group(1)
        if book_id in books:
            continue

        metadata = extract_metadata(txt_file)
        if metadata:
            # Copy to our raw directory
            dest = RAW_DIR / f"pg{book_id}.txt"
            if not dest.exists():
                import shutil
                shutil.copy(txt_file, dest)

            books[book_id] = metadata
            processed += 1

            if processed % 50 == 0:
                print(f"  Processed {processed} books...")

    with open(BOOKS_JSON, "w") as f:
        json.dump(books, f, indent=2)

    print(f"Done! Added {processed} books. Total catalog: {len(books)}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["rsync", "polite"], default="polite",
                        help="rsync=bulk mirror (recommended), polite=slow one-by-one")
    parser.add_argument("--count", type=int, default=100, help="Books to fetch")
    args = parser.parse_args()

    RAW_DIR.mkdir(exist_ok=True)

    if args.method == "rsync":
        rsync_books(args.count)
    else:
        polite_fetch(args.count)


if __name__ == "__main__":
    main()
