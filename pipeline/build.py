#!/usr/bin/env python3
"""
Serendipity pipeline: build cards from Gutenberg texts.

Usage:
    python build.py              # Process all books in raw/
    python build.py --stats      # Show stats without writing output
    python build.py --sample 20  # Output sample of N cards per book for review

Content Strategy:
    - "standalone" books (philosophy, aphorisms, essays): extract all sections
    - Linear narratives (novels, stories): only extract opening paragraphs
    - Each card tagged with content_type for feed weighting
"""

import json
import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Optional

from chunker import process_text, generate_card_id, Chunk
from filters import filter_chunk, filter_chunk_all_reasons

# How many opening chunks to extract from linear (non-standalone) books
# Just 1 = the opening hook only (first ~300 words)
OPENING_CHUNKS_LIMIT = 1

# Paths
PIPELINE_DIR = Path(__file__).parent
RAW_DIR = PIPELINE_DIR / "raw"
BOOKS_JSON = PIPELINE_DIR / "books.json"
OUTPUT_DIR = PIPELINE_DIR.parent / "web" / "data"

# For review harness
REJECTED_SAMPLE_SIZE = 100  # Per reject reason


def load_books_metadata() -> dict:
    """Load books.json sidecar."""
    if not BOOKS_JSON.exists():
        print(f"ERROR: {BOOKS_JSON} not found")
        sys.exit(1)

    with open(BOOKS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_raw_files() -> list[tuple[str, Path]]:
    """Find pg*.txt files in raw/, return (gutenberg_id, path) pairs."""
    if not RAW_DIR.exists():
        print(f"ERROR: {RAW_DIR} not found. Create it and add .txt files.")
        sys.exit(1)

    files = []
    for path in RAW_DIR.glob("pg*.txt"):
        # Extract ID from filename: pg1234.txt -> 1234
        match = re.match(r'pg(\d+)\.txt', path.name)
        if match:
            files.append((match.group(1), path))

    return sorted(files, key=lambda x: int(x[0]))


def validate_path(filepath: Path) -> bool:
    """Check for path traversal attacks."""
    try:
        # Resolve to absolute and check it's under RAW_DIR
        resolved = filepath.resolve()
        return str(resolved).startswith(str(RAW_DIR.resolve()))
    except (OSError, ValueError):
        return False


def classify_content_type(seq: int, form: str, is_standalone: bool, has_section: bool) -> str:
    """
    Determine content_type for a card based on its position and book type.

    Returns: "opening", "section", "passage"
    """
    if seq == 0:
        return "opening"
    elif form == "sectioned" and has_section:
        return "section"
    else:
        return "passage"


def process_book(
    gutenberg_id: str,
    filepath: Path,
    metadata: dict,
    collect_rejected: bool = True
) -> tuple[list[dict], list[dict], dict]:
    """
    Process a single book.

    For standalone books (philosophy, aphorisms, essays): extract all sections
    For linear books (novels, stories): only extract opening paragraphs

    Returns:
        (accepted_cards, rejected_chunks, stats_dict)
    """
    if not validate_path(filepath):
        print(f"  SKIP: Invalid path {filepath}")
        return [], [], {"error": "invalid_path"}

    form = metadata.get("form", "prose")
    is_standalone = metadata.get("standalone", False)

    # Sectioned texts are implicitly standalone (each section works alone)
    if form == "sectioned":
        is_standalone = True

    if form == "verse":
        print(f"  SKIP: verse form not supported in v1")
        return [], [], {"skipped": "verse"}

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw_text = f.read()
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return [], [], {"error": str(e)}

    accepted = []
    rejected = []
    reject_reasons = defaultdict(int)
    skipped_linear = 0

    seq = 0
    for chunk in process_text(raw_text, form, gutenberg_id):
        # For non-standalone (linear) books, only keep opening chunks
        if not is_standalone and seq >= OPENING_CHUNKS_LIMIT:
            skipped_linear += 1
            continue

        # Run filters
        reject_reason = filter_chunk(chunk.text, form)

        if reject_reason:
            reject_reasons[reject_reason.split('(')[0].strip()] += 1
            if collect_rejected:
                rejected.append({
                    "text": chunk.text[:2000],  # Truncate for review
                    "reason": reject_reason,
                    "book_id": gutenberg_id,
                    "form": form,
                })
        else:
            card_id = generate_card_id(gutenberg_id, chunk.char_offset)
            has_section = chunk.section_num is not None
            content_type = classify_content_type(seq, form, is_standalone, has_section)

            card = {
                "id": card_id,
                "book_id": gutenberg_id,
                "seq": seq,
                "text": chunk.text,
                "source_title": metadata.get("title", "Unknown"),
                "author": metadata.get("author", "Unknown"),
                "era": metadata.get("era", ""),
                "topic": metadata.get("topic", "general"),
                "form": form,
                "content_type": content_type,
                "standalone": is_standalone,
                "source_url": f"https://www.gutenberg.org/ebooks/{gutenberg_id}",
                "description": metadata.get("description", ""),
            }
            if chunk.section_num:
                card["section"] = chunk.section_num
            accepted.append(card)
            seq += 1

    stats = {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "reject_reasons": dict(reject_reasons),
        "skipped_linear": skipped_linear,
    }

    if skipped_linear > 0:
        print(f"  (Skipped {skipped_linear} non-opening chunks from linear narrative)")

    return accepted, rejected, stats


def build_shards(all_cards: list[dict], target_size_kb: int = 300) -> dict[str, list[dict]]:
    """
    Split cards into shards by topic, targeting ~300KB per shard.
    """
    # Group by topic
    by_topic = defaultdict(list)
    for card in all_cards:
        by_topic[card["topic"]].append(card)

    shards = {}
    for topic, cards in by_topic.items():
        # Estimate size and split if needed
        json_size = len(json.dumps(cards))
        num_shards = max(1, json_size // (target_size_kb * 1024) + 1)

        if num_shards == 1:
            shards[f"{topic}"] = cards
        else:
            # Split into roughly equal shards
            per_shard = len(cards) // num_shards + 1
            for i in range(num_shards):
                start = i * per_shard
                end = start + per_shard
                shard_cards = cards[start:end]
                if shard_cards:
                    shards[f"{topic}_{i+1}"] = shard_cards

    return shards


def write_output(shards: dict, rejected_sample: list[dict]):
    """Write shards and manifest to web/data/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write shards
    manifest_shards = []
    total_cards = 0

    for shard_name, cards in shards.items():
        filename = f"{shard_name}.json"
        filepath = OUTPUT_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cards, f, ensure_ascii=False)

        size_kb = filepath.stat().st_size / 1024
        topics = list(set(c["topic"] for c in cards))

        manifest_shards.append({
            "file": filename,
            "cards": len(cards),
            "size_kb": round(size_kb, 1),
            "topics": topics,
        })
        total_cards += len(cards)
        print(f"  Wrote {filename}: {len(cards)} cards, {size_kb:.1f}KB")

    # Write manifest
    manifest = {
        "version": "1.0.0",
        "total_cards": total_cards,
        "shards": manifest_shards,
        "topics": list(set(t for s in manifest_shards for t in s["topics"])),
    }

    with open(OUTPUT_DIR / "manifest.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"  Wrote manifest.json: {total_cards} total cards")

    # Write rejected sample for review harness
    if rejected_sample:
        with open(PIPELINE_DIR / "rejected.json", 'w', encoding='utf-8') as f:
            json.dump(rejected_sample, f, indent=2, ensure_ascii=False)
        print(f"  Wrote rejected.json: {len(rejected_sample)} samples")


def main():
    parser = argparse.ArgumentParser(description="Build Serendipity card corpus")
    parser.add_argument("--stats", action="store_true",
                        help="Show stats without writing output")
    parser.add_argument("--sample", type=int, default=0,
                        help="Limit to N cards per book for review")
    args = parser.parse_args()

    print("Serendipity Pipeline")
    print("=" * 50)

    # Load metadata
    books_meta = load_books_metadata()
    print(f"Loaded {len(books_meta)} book entries from books.json")

    # Find raw files
    raw_files = find_raw_files()
    print(f"Found {len(raw_files)} files in raw/")

    if not raw_files:
        print("\nNo pg*.txt files found. Add Gutenberg texts to pipeline/raw/")
        print("Filename format: pg{id}.txt (e.g., pg1998.txt)")
        return

    all_cards = []
    all_rejected = []
    total_stats = defaultdict(int)

    print("\nProcessing books:")
    print("-" * 50)

    for gutenberg_id, filepath in raw_files:
        if gutenberg_id not in books_meta:
            print(f"\n[pg{gutenberg_id}] WARNING: No books.json entry, skipping")
            continue

        meta = books_meta[gutenberg_id]
        print(f"\n[pg{gutenberg_id}] {meta.get('title', 'Unknown')}")
        print(f"  Form: {meta.get('form', 'prose')}")

        cards, rejected, stats = process_book(gutenberg_id, filepath, meta)

        if args.sample and cards:
            cards = cards[:args.sample]

        all_cards.extend(cards)
        all_rejected.extend(rejected[:REJECTED_SAMPLE_SIZE])

        print(f"  Accepted: {stats.get('accepted', 0)}")
        print(f"  Rejected: {stats.get('rejected', 0)}")

        if stats.get('reject_reasons'):
            print("  Reject breakdown:")
            for reason, count in sorted(stats['reject_reasons'].items(),
                                         key=lambda x: -x[1]):
                print(f"    {reason}: {count}")

        total_stats['accepted'] += stats.get('accepted', 0)
        total_stats['rejected'] += stats.get('rejected', 0)

    print("\n" + "=" * 50)
    print(f"TOTAL: {total_stats['accepted']} accepted, {total_stats['rejected']} rejected")

    if args.stats:
        print("\n(--stats mode: no files written)")
        return

    if not all_cards:
        print("\nNo cards produced. Check your raw/ files and books.json.")
        return

    # Build shards and write output
    print("\nWriting output:")
    print("-" * 50)
    shards = build_shards(all_cards)
    write_output(shards, all_rejected)

    print("\nDone! Use review.html to inspect accepted/rejected samples.")


if __name__ == "__main__":
    main()
