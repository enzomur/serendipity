#!/usr/bin/env python3
"""
Import books from gutenberg_mirror/ to raw/ with proper naming.
Prefers UTF-8 encoded versions (-0.txt suffix).
"""

import os
import re
import shutil
import json
from pathlib import Path
from collections import defaultdict

PIPELINE_DIR = Path(__file__).parent
MIRROR_DIR = PIPELINE_DIR / "gutenberg_mirror"
RAW_DIR = PIPELINE_DIR / "raw"
BOOKS_JSON = PIPELINE_DIR / "books.json"

def extract_gutenberg_id(filepath: Path) -> str | None:
    """Extract Gutenberg ID from mirror path or filename."""
    # Try to get ID from directory structure (e.g., /1/2/3/4/12345/12345.txt)
    parts = filepath.parts

    # Look for numeric directory that matches filename pattern
    filename = filepath.stem

    # Common patterns: 12345.txt, 12345-0.txt, 12345-8.txt
    match = re.match(r'^(\d+)(-\d)?$', filename)
    if match:
        return match.group(1)

    # Also check parent directory name
    for part in reversed(parts):
        if part.isdigit():
            return part

    return None

def get_best_version(files_by_id: dict[str, list[Path]]) -> dict[str, Path]:
    """For each ID, pick the best file version (prefer -0.txt for UTF-8)."""
    best = {}

    for gid, files in files_by_id.items():
        # Priority: -0.txt (UTF-8) > plain .txt > -8.txt (Latin-1)
        scored = []
        for f in files:
            name = f.name
            if '-0.txt' in name:
                score = 3
            elif re.match(r'^\d+\.txt$', name):
                score = 2
            else:
                score = 1
            # Prefer files not in 'old' directories
            if 'old' in str(f):
                score -= 0.5
            scored.append((score, f.stat().st_size, f))

        # Sort by score desc, then size desc (bigger = more complete)
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best[gid] = scored[0][2]

    return best

def main():
    print("Importing books from gutenberg_mirror/")
    print("=" * 50)

    # Find all .txt files in mirror
    all_files = list(MIRROR_DIR.rglob("*.txt"))
    print(f"Found {len(all_files)} .txt files in mirror")

    # Group by Gutenberg ID
    files_by_id = defaultdict(list)
    for f in all_files:
        gid = extract_gutenberg_id(f)
        if gid and gid.isdigit():
            files_by_id[gid].append(f)

    print(f"Found {len(files_by_id)} unique Gutenberg IDs")

    # Get existing raw files
    existing = set()
    for f in RAW_DIR.glob("pg*.txt"):
        match = re.match(r'pg(\d+)\.txt', f.name)
        if match:
            existing.add(match.group(1))

    print(f"Already have {len(existing)} books in raw/")

    # Pick best version for each ID
    best_versions = get_best_version(files_by_id)

    # Copy new files
    copied = 0
    skipped = 0

    for gid, src_path in sorted(best_versions.items(), key=lambda x: int(x[0])):
        if gid in existing:
            skipped += 1
            continue

        dst_path = RAW_DIR / f"pg{gid}.txt"
        try:
            shutil.copy2(src_path, dst_path)
            copied += 1
            if copied <= 20 or copied % 100 == 0:
                print(f"  Copied pg{gid}.txt")
        except Exception as e:
            print(f"  ERROR copying {gid}: {e}")

    print(f"\nCopied {copied} new books, skipped {skipped} existing")
    print(f"Total books in raw/: {len(existing) + copied}")

if __name__ == "__main__":
    main()
