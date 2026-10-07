# Serendipity - Project Context

## What This Is
A swipeable feed of public-domain wisdom from Project Gutenberg. No backend, no accounts, no tracking. Works as a PWA on iOS.

## Current State (Aug 14, 2025)

### Data Pipeline - COMPLETE
- **241,576 cards** generated from 2,170 books
- **639 MB** of card data in `web/data/`
- Topics: literature, philosophy, religion, science, economics, history
- Mirror: `pipeline/gutenberg_mirror/` (1.8GB, 5,491 files)
- Catalog: `pipeline/books.json` (2,145 entries)

### Rsync Command (to resume if interrupted)
```bash
cd /Users/lorenzom/Desktop/serendipity/pipeline
rsync -avz --include="*/" --include="*.txt" --exclude="*" --max-size=2M \
  rsync://aleph.gutenberg.org/gutenberg/ gutenberg_mirror/
```

### Next Steps
1. UI/UX improvements
2. Topic filtering/discovery
3. Offline PWA optimization for 639MB corpus

## Project Structure
```
serendipity/
├── web/           # Frontend (static HTML/JS/CSS PWA)
├── pipeline/      # Data processing
│   ├── books.json         # Book metadata catalog
│   ├── gutenberg_mirror/  # Downloaded Gutenberg texts
│   ├── build.py           # Processing pipeline
│   ├── filters.py         # Text quality filters
│   └── review.html        # Review processed chunks
└── README.md
```

## Text Forms
- **prose** - Novels, treatises. Chunks by word count.
- **sectioned** - Numbered aphorisms (Meditations, Tao Te Ching). One section per card.
- **verse** - Poetry. Not yet supported.

## Running Locally
```bash
python3 -m http.server 8000
# Open http://localhost:8000/web/
```
