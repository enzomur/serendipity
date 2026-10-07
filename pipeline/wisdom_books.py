#!/usr/bin/env python3
"""
Fetch wisdom and philosophy texts from Project Gutenberg.

These are texts where every section/page can stand alone:
- Philosophy (ancient, modern, eastern, western)
- Wisdom literature
- Essays and letters
- Religious/spiritual texts
- Aphorisms and maxims
"""

import json
import os
import re
import urllib.request
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
RAW_DIR = PIPELINE_DIR / "raw"
BOOKS_JSON = PIPELINE_DIR / "books.json"

# Curated list of wisdom/philosophy texts from Gutenberg
# Format: (gutenberg_id, title, author, era, topic, form, description)
WISDOM_TEXTS = [
    # Ancient Philosophy
    ("1656", "Essays", "Michel de Montaigne", "16th century", "philosophy", "sectioned",
     "The inventor of the essay form reflects on life, death, and human nature."),
    ("10615", "Seneca's Letters from a Stoic", "Seneca", "1st century", "philosophy", "sectioned",
     "Practical Stoic wisdom on living well, facing death, and finding tranquility."),
    ("45109", "The Discourses of Epictetus", "Epictetus", "2nd century", "philosophy", "sectioned",
     "A former slave's teachings on what we can control and what we cannot."),
    ("2680", "Meditations", "Marcus Aurelius", "2nd century", "philosophy", "sectioned",
     "A Roman emperor's private journal of Stoic self-improvement."),
    ("1497", "The Republic", "Plato", "4th century BCE", "philosophy", "sectioned",
     "Socratic dialogues on justice, the ideal state, and the nature of reality."),
    ("1656", "Apology", "Plato", "4th century BCE", "philosophy", "sectioned",
     "Socrates defends himself and philosophy itself at his trial."),
    ("1672", "Phaedo", "Plato", "4th century BCE", "philosophy", "sectioned",
     "Socrates' final hours and arguments for the immortality of the soul."),
    ("1600", "Symposium", "Plato", "4th century BCE", "philosophy", "sectioned",
     "A dinner party where guests give speeches on the nature of love."),
    ("6762", "Nicomachean Ethics", "Aristotle", "4th century BCE", "philosophy", "sectioned",
     "What it means to live a good life and cultivate virtue."),

    # Eastern Philosophy
    ("216", "Tao Te Ching", "Lao Tzu", "6th century BCE", "philosophy", "sectioned",
     "Ancient Chinese text on living in harmony with the natural way."),
    ("4094", "The Analects", "Confucius", "5th century BCE", "philosophy", "sectioned",
     "Sayings and ideas of China's most influential philosopher."),
    ("2500", "Siddhartha", "Hermann Hesse", "20th century", "philosophy", "prose",
     "A spiritual journey to enlightenment in ancient India."),
    ("7350", "The Dhammapada", "Buddha", "5th century BCE", "religion", "sectioned",
     "Core teachings of Buddhism in verse form."),
    ("11995", "The Upanishads", "Various", "8th-4th century BCE", "religion", "sectioned",
     "Hindu philosophical texts on the nature of reality and the self."),
    ("2388", "Bhagavad Gita", "Vyasa", "2nd century BCE", "religion", "sectioned",
     "Krishna's teachings on duty, action, and the nature of existence."),

    # Modern Philosophy
    ("1232", "The Prince", "Niccolò Machiavelli", "16th century", "philosophy", "sectioned",
     "A ruthlessly practical guide to acquiring and maintaining political power."),
    ("4363", "Beyond Good and Evil", "Friedrich Nietzsche", "19th century", "philosophy", "sectioned",
     "A critique of traditional morality and the nature of truth."),
    ("1998", "Thus Spake Zarathustra", "Friedrich Nietzsche", "19th century", "philosophy", "sectioned",
     "Nietzsche's philosophical novel on the death of God and the Übermensch."),
    ("4280", "Twilight of the Idols", "Friedrich Nietzsche", "19th century", "philosophy", "sectioned",
     "A critique of Western philosophy and culture."),
    ("5827", "The Genealogy of Morals", "Friedrich Nietzsche", "19th century", "philosophy", "sectioned",
     "An investigation into the origins of moral concepts."),
    ("37090", "Pensées", "Blaise Pascal", "17th century", "philosophy", "sectioned",
     "Fragments of profound thought on faith, reason, and human nature."),
    ("9662", "Maxims", "François de La Rochefoucauld", "17th century", "philosophy", "sectioned",
     "Sharp observations on human nature and self-interest."),
    ("2130", "The Art of Worldly Wisdom", "Baltasar Gracián", "17th century", "philosophy", "sectioned",
     "300 aphorisms on success, prudence, and navigating life."),

    # Essays and Letters
    ("575", "Essays of Ralph Waldo Emerson", "Ralph Waldo Emerson", "19th century", "philosophy", "sectioned",
     "Transcendentalist essays on self-reliance, nature, and the American spirit."),
    ("16643", "Self-Reliance and Other Essays", "Ralph Waldo Emerson", "19th century", "philosophy", "sectioned",
     "The foundational text of American individualism."),
    ("2350", "Essays of Francis Bacon", "Francis Bacon", "17th century", "philosophy", "sectioned",
     "Pithy essays on truth, death, love, and the art of living."),
    ("5669", "Moral Letters to Lucilius", "Seneca", "1st century", "philosophy", "sectioned",
     "Letters of practical Stoic advice to a young friend."),
    ("852", "The Autobiography of Benjamin Franklin", "Benjamin Franklin", "18th century", "philosophy", "sectioned",
     "Wit and wisdom from America's first self-made man."),

    # Religious/Wisdom Literature
    ("10", "The King James Bible", "Various", "17th century", "religion", "sectioned",
     "The foundational English translation of Christian scripture."),
    ("2321", "The Book of Common Prayer", "Church of England", "16th century", "religion", "sectioned",
     "Historic prayers and liturgy of the Anglican tradition."),
    ("7849", "Ecclesiastes", "Solomon", "3rd century BCE", "religion", "sectioned",
     "Ancient wisdom on the meaning of life: vanity of vanities."),
    ("8300", "The Book of Proverbs", "Solomon", "10th century BCE", "religion", "sectioned",
     "Ancient Hebrew wisdom on righteous living."),
    ("2680", "The Imitation of Christ", "Thomas à Kempis", "15th century", "religion", "sectioned",
     "Medieval Christian guide to spiritual perfection."),

    # Stoicism
    ("10661", "Of Peace of Mind", "Seneca", "1st century", "philosophy", "sectioned",
     "Finding tranquility amid life's storms."),
    ("3052", "On the Shortness of Life", "Seneca", "1st century", "philosophy", "sectioned",
     "Life is long enough if we use it well."),

    # Existentialism and Modern Thought
    ("5740", "The Problems of Philosophy", "Bertrand Russell", "20th century", "philosophy", "sectioned",
     "A clear introduction to fundamental philosophical questions."),
    ("37727", "The Myth of Sisyphus", "Albert Camus", "20th century", "philosophy", "prose",
     "Must we imagine Sisyphus happy? On the absurd and suicide."),

    # Asian Classics
    ("17157", "The Art of War", "Sun Tzu", "5th century BCE", "philosophy", "sectioned",
     "Ancient Chinese treatise on strategy, still relevant today."),
    ("4650", "The Book of Tea", "Kakuzo Okakura", "20th century", "philosophy", "sectioned",
     "Japanese aesthetics and the philosophy of tea."),
    ("30867", "Bushido, the Soul of Japan", "Inazo Nitobe", "20th century", "philosophy", "sectioned",
     "The samurai code of honor and its influence on Japanese culture."),

    # Wisdom Collections
    ("18269", "The Golden Sayings of Epictetus", "Epictetus", "2nd century", "philosophy", "sectioned",
     "Concentrated Stoic wisdom in bite-sized form."),
    ("2816", "The Autobiography of a Yogi", "Paramahansa Yogananda", "20th century", "religion", "prose",
     "Spiritual classic introducing yoga and meditation to the West."),
]


def fetch_book(gid: str, title: str) -> bool:
    """Download a book from Gutenberg if not already present."""
    filepath = RAW_DIR / f"pg{gid}.txt"

    if filepath.exists():
        print(f"  Already have pg{gid}.txt")
        return True

    # Try different Gutenberg URL formats
    urls = [
        f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}.txt",
    ]

    for url in urls:
        try:
            print(f"  Fetching {url}...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Serendipity/1.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode('utf-8', errors='replace')

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"  Downloaded pg{gid}.txt ({len(content)} bytes)")
            return True
        except Exception as e:
            continue

    print(f"  FAILED to download {title} (pg{gid})")
    return False


def update_books_json(gid: str, title: str, author: str, era: str, topic: str, form: str, description: str):
    """Add or update a book entry in books.json."""
    with open(BOOKS_JSON, 'r', encoding='utf-8') as f:
        books = json.load(f)

    books[gid] = {
        "title": title,
        "author": author,
        "era": era,
        "topic": topic,
        "form": form,
        "description": description,
        "standalone": True  # All wisdom texts are standalone
    }

    with open(BOOKS_JSON, 'w', encoding='utf-8') as f:
        json.dump(books, f, indent=2, ensure_ascii=False)


def main():
    RAW_DIR.mkdir(exist_ok=True)

    print("Fetching wisdom and philosophy texts from Gutenberg")
    print("=" * 60)

    success = 0
    failed = 0

    for entry in WISDOM_TEXTS:
        gid, title, author, era, topic, form, description = entry
        print(f"\n[{gid}] {title} by {author}")

        if fetch_book(gid, title):
            update_books_json(gid, title, author, era, topic, form, description)
            success += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Done: {success} books ready, {failed} failed")
    print("\nRun 'python build.py' to regenerate cards")


if __name__ == "__main__":
    main()
