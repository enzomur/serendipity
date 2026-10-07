# Serendipity

A swipeable feed of public-domain wisdom. No backend, no accounts, no tracking.

## Quick Start

```bash
# Serve locally
cd serendipity
python3 -m http.server 8000

# Open http://localhost:8000/web/
```

## Adding Books

1. Download `.txt` files from [Project Gutenberg](https://www.gutenberg.org)
2. Save them to `pipeline/raw/` as `pg{id}.txt` (e.g., `pg2680.txt`)
3. Add metadata to `pipeline/books.json`:

```json
{
  "2680": {
    "title": "Meditations",
    "author": "Marcus Aurelius",
    "era": "2nd century",
    "topic": "philosophy",
    "form": "sectioned"
  }
}
```

4. Run the pipeline:

```bash
cd pipeline
python3 build.py
```

5. Review output: open `http://localhost:8000/pipeline/review.html`

## Text Forms

- **prose** — Standard paragraphs (novels, treatises). Chunks by word count.
- **sectioned** — Numbered aphorisms (Meditations, Tao Te Ching). One section per card.
- **verse** — Poetry. Not yet supported (skipped with warning).

## Filter Tuning

Edit thresholds in `pipeline/filters.py` under `FILTER_CONFIG`. Run tests:

```bash
python3 test_filters.py
```

## Deploy

Works on any static host. Just upload the `web/` folder:

- **GitHub Pages**: Push to `gh-pages` branch
- **Cloudflare Pages**: Connect repo, set build output to `web/`
- **Netlify**: Drag and drop `web/` folder

## iOS PWA

Add to Home Screen from Safari. The app works offline after first load.

## Export Saves

Menu → Export saves. Creates a JSON backup of your saved cards. Import works too.
