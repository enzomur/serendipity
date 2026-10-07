#!/usr/bin/env python3
"""
Fetch books from Project Gutenberg with auto-generated metadata.
Usage: python fetch_books.py [--count N]
"""

import json
import os
import re
import time
import urllib.request
from pathlib import Path

# Curated list of high-quality public domain books by category
# Format: (id, title, author, era, topic, form, description)
BOOK_CATALOG = [
    # Philosophy
    (1497, "The Republic", "Plato", "4th century BCE", "philosophy", "prose",
     "Socratic dialogue on justice, the ideal state, and the nature of reality."),
    (1656, "Essays", "Michel de Montaigne", "16th century", "philosophy", "prose",
     "Personal reflections that invented the essay as a literary form."),
    (4280, "Critique of Pure Reason", "Immanuel Kant", "18th century", "philosophy", "prose",
     "Kant's examination of the limits and possibilities of human knowledge."),
    (4363, "Beyond Good and Evil", "Friedrich Nietzsche", "19th century", "philosophy", "sectioned",
     "A critique of traditional morality and the philosophers who preach it."),
    (5682, "The Critique of Practical Reason", "Immanuel Kant", "18th century", "philosophy", "prose",
     "Kant's moral philosophy and the categorical imperative."),
    (10615, "The Ethics", "Baruch Spinoza", "17th century", "philosophy", "sectioned",
     "A geometric proof of God, nature, and human freedom."),
    (11224, "The Social Contract", "Jean-Jacques Rousseau", "18th century", "philosophy", "prose",
     "The foundational text of modern democratic theory."),
    (17147, "Discourse on Method", "René Descartes", "17th century", "philosophy", "prose",
     "I think, therefore I am — the foundation of modern philosophy."),
    (26091, "Utilitarianism", "John Stuart Mill", "19th century", "philosophy", "prose",
     "The greatest good for the greatest number."),
    (34901, "On Liberty", "John Stuart Mill", "19th century", "philosophy", "prose",
     "A defense of individual freedom against tyranny of the majority."),
    (37090, "The Will to Believe", "William James", "19th century", "philosophy", "prose",
     "Pragmatist defense of faith and the right to believe."),
    (52821, "An Enquiry Concerning Human Understanding", "David Hume", "18th century", "philosophy", "prose",
     "Skeptical examination of causation, miracles, and knowledge."),
    (55201, "Being and Time", "Martin Heidegger", "20th century", "philosophy", "prose",
     "Existentialist analysis of human existence and temporality."),
    (59241, "Phenomenology of Spirit", "G.W.F. Hegel", "19th century", "philosophy", "prose",
     "The dialectical journey of consciousness toward absolute knowledge."),

    # History
    (731, "The Decline and Fall of the Roman Empire Vol 1", "Edward Gibbon", "18th century", "history", "prose",
     "Monumental history of Rome's collapse over a thousand years."),
    (890, "The Federalist Papers", "Hamilton, Madison, Jay", "18th century", "history", "prose",
     "The philosophical foundation of the American Constitution."),
    (1399, "Anna Karenina", "Leo Tolstoy", "19th century", "literature", "prose",
     "Tragic tale of love, society, and self-destruction in Russian aristocracy."),
    (2097, "The Autobiography of Benjamin Franklin", "Benjamin Franklin", "18th century", "history", "prose",
     "A founding father's self-made journey from poverty to greatness."),
    (2680, "Meditations", "Marcus Aurelius", "2nd century", "philosophy", "sectioned",
     "Private reflections of a Roman emperor on Stoic self-discipline."),
    (3296, "The Confessions", "Jean-Jacques Rousseau", "18th century", "philosophy", "prose",
     "Brutally honest autobiography that invented the modern memoir."),
    (6130, "The Iliad", "Homer", "8th century BCE", "literature", "prose",
     "The rage of Achilles and the tragedy of the Trojan War."),
    (6867, "Walden", "Henry David Thoreau", "19th century", "philosophy", "prose",
     "Two years of simple living and self-reliance at Walden Pond."),
    (7370, "The Odyssey", "Homer", "8th century BCE", "literature", "prose",
     "Odysseus's ten-year journey home after the Trojan War."),
    (8438, "The Koran (Rodwell)", "Various", "7th century", "religion", "sectioned",
     "The central religious text of Islam, believed to be divine revelation."),
    (10800, "The Twelve Caesars", "Suetonius", "2nd century", "history", "prose",
     "Scandalous biographies of Rome's first twelve emperors."),
    (16452, "The Annals", "Tacitus", "2nd century", "history", "prose",
     "A senator's dark chronicle of the early Roman Empire."),
    (25717, "The Histories", "Herodotus", "5th century BCE", "history", "prose",
     "The first work of history, covering the Persian Wars."),
    (28520, "The Prince", "Niccolò Machiavelli", "16th century", "philosophy", "prose",
     "A ruthlessly practical guide to acquiring and maintaining political power."),

    # Science
    (2009, "The Origin of Species", "Charles Darwin", "19th century", "science", "prose",
     "The work that established evolution by natural selection."),
    (14725, "The Descent of Man", "Charles Darwin", "19th century", "science", "prose",
     "Darwin applies evolution to human origins and sexual selection."),
    (15489, "The Voyage of the Beagle", "Charles Darwin", "19th century", "science", "prose",
     "Darwin's journal of the expedition that inspired evolution."),
    (30155, "Relativity: The Special and General Theory", "Albert Einstein", "20th century", "science", "prose",
     "Einstein explains his revolutionary theories in accessible terms."),
    (37157, "The Interpretation of Dreams", "Sigmund Freud", "20th century", "science", "prose",
     "Freud's founding work of psychoanalysis."),
    (38427, "The Principles of Psychology", "William James", "19th century", "science", "prose",
     "The foundational text of American psychology."),
    (45502, "Principia Mathematica", "Isaac Newton", "17th century", "science", "prose",
     "The laws of motion and gravitation that defined modern physics."),

    # Literature - Novels
    (11, "Alice's Adventures in Wonderland", "Lewis Carroll", "19th century", "literature", "prose",
     "A girl falls down a rabbit hole into a world of absurdist logic."),
    (16, "Peter Pan", "J.M. Barrie", "20th century", "literature", "prose",
     "The boy who never grows up and the children who follow him to Neverland."),
    (74, "The Adventures of Tom Sawyer", "Mark Twain", "19th century", "literature", "prose",
     "Mischief and adventure along the Mississippi River."),
    (76, "Adventures of Huckleberry Finn", "Mark Twain", "19th century", "literature", "prose",
     "A boy and an escaped slave raft down the Mississippi."),
    (120, "Treasure Island", "Robert Louis Stevenson", "19th century", "literature", "prose",
     "Pirates, buried gold, and a young boy's adventure at sea."),
    (135, "Les Misérables", "Victor Hugo", "19th century", "literature", "prose",
     "An ex-convict's redemption against the backdrop of revolutionary France."),
    (158, "Emma", "Jane Austen", "19th century", "literature", "prose",
     "A clever young woman learns the perils of matchmaking."),
    (161, "Sense and Sensibility", "Jane Austen", "19th century", "literature", "prose",
     "Two sisters navigate love, heartbreak, and financial ruin."),
    (219, "Heart of Darkness", "Joseph Conrad", "19th century", "literature", "prose",
     "A journey upriver into colonial Africa and human depravity."),
    (244, "A Study in Scarlet", "Arthur Conan Doyle", "19th century", "literature", "prose",
     "The first Sherlock Holmes novel — a murder with roots in Utah."),
    (345, "Dracula", "Bram Stoker", "19th century", "literature", "prose",
     "The classic vampire tale told through letters and journal entries."),
    (730, "Oliver Twist", "Charles Dickens", "19th century", "literature", "prose",
     "An orphan's journey through London's criminal underworld."),
    (766, "David Copperfield", "Charles Dickens", "19th century", "literature", "prose",
     "Dickens's most autobiographical novel of a boy's journey to manhood."),
    (768, "Wuthering Heights", "Emily Brontë", "19th century", "literature", "prose",
     "Obsessive love and revenge on the Yorkshire moors."),
    (844, "The Importance of Being Earnest", "Oscar Wilde", "19th century", "literature", "prose",
     "A farcical comedy of mistaken identity and trivial matters."),
    (1080, "A Modest Proposal", "Jonathan Swift", "18th century", "literature", "prose",
     "Savage satire suggesting the Irish eat their children."),
    (1184, "The Count of Monte Cristo", "Alexandre Dumas", "19th century", "literature", "prose",
     "A man unjustly imprisoned escapes to exact elaborate revenge."),
    (1260, "Jane Eyre", "Charlotte Brontë", "19th century", "literature", "prose",
     "A governess falls for her brooding employer with a dark secret."),
    (1400, "Great Expectations", "Charles Dickens", "19th century", "literature", "prose",
     "A poor boy's journey to become a gentleman in Victorian England."),
    (1952, "The Yellow Wallpaper", "Charlotte Perkins Gilman", "19th century", "literature", "prose",
     "A woman's descent into madness under the rest cure."),
    (2147, "The Red Badge of Courage", "Stephen Crane", "19th century", "literature", "prose",
     "A young soldier faces fear and cowardice in the Civil War."),
    (2148, "The Awakening", "Kate Chopin", "19th century", "literature", "prose",
     "A woman's sexual and spiritual awakening in Creole Louisiana."),
    (2591, "Grimms' Fairy Tales", "Brothers Grimm", "19th century", "literature", "prose",
     "The original dark fairy tales before Disney."),
    (2814, "Dubliners", "James Joyce", "20th century", "literature", "prose",
     "Fifteen stories of paralysis and epiphany in Dublin."),
    (4300, "Ulysses", "James Joyce", "20th century", "literature", "prose",
     "A day in Dublin rendered in revolutionary stream of consciousness."),
    (5200, "Metamorphosis", "Franz Kafka", "20th century", "literature", "prose",
     "A man wakes up transformed into a giant insect."),
    (11030, "The Brothers Karamazov", "Fyodor Dostoevsky", "19th century", "literature", "prose",
     "Faith, doubt, and murder in a Russian family."),
    (28054, "Crime and Punishment", "Fyodor Dostoevsky", "19th century", "literature", "prose",
     "A student commits murder and descends into psychological torment."),
    (36034, "Notes from Underground", "Fyodor Dostoevsky", "19th century", "literature", "prose",
     "The bitter confessions of a spiteful, isolated man."),

    # Poetry and Essays
    (1321, "Paradise Lost", "John Milton", "17th century", "literature", "verse",
     "Satan's fall and the loss of Eden in epic blank verse."),
    (2264, "Macbeth", "William Shakespeare", "17th century", "literature", "verse",
     "Ambition, murder, and madness in medieval Scotland."),
    (1041, "Shakespeare's Sonnets", "William Shakespeare", "17th century", "literature", "verse",
     "154 poems on love, beauty, mortality, and time."),
    (1112, "The Tragedy of Romeo and Juliet", "William Shakespeare", "16th century", "literature", "verse",
     "Star-crossed lovers and feuding families in Verona."),
    (2267, "Hamlet", "William Shakespeare", "17th century", "literature", "verse",
     "A prince feigns madness while plotting revenge for his father's murder."),
    (1790, "King Lear", "William Shakespeare", "17th century", "literature", "verse",
     "An aging king divides his kingdom and descends into madness."),
    (23042, "Othello", "William Shakespeare", "17th century", "literature", "verse",
     "Jealousy destroys a Moorish general and his innocent wife."),

    # Eastern Philosophy & Religion
    (216, "Tao Te Ching", "Lao Tzu", "6th century BCE", "philosophy", "sectioned",
     "Ancient Chinese text on living in harmony with the natural way."),
    (4094, "The Analects", "Confucius", "5th century BCE", "philosophy", "sectioned",
     "Sayings and teachings on ethics, family, and good governance."),
    (2500, "Siddhartha", "Hermann Hesse", "20th century", "philosophy", "prose",
     "A young man's spiritual journey in ancient India."),
    (678, "The Bhagavad Gita", "Vyasa", "2nd century BCE", "religion", "sectioned",
     "Hindu scripture on duty, devotion, and the nature of reality."),
    (45847, "The Enchiridion", "Epictetus", "2nd century", "philosophy", "sectioned",
     "A Stoic handbook on what is and isn't within our control."),
]

RAW_DIR = Path(__file__).parent / "raw"
BOOKS_JSON = Path(__file__).parent / "books.json"


def download_book(book_id: int) -> bool:
    """Download a single book from Gutenberg."""
    filepath = RAW_DIR / f"pg{book_id}.txt"
    if filepath.exists():
        print(f"  Already have pg{book_id}")
        return True

    url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
    try:
        urllib.request.urlretrieve(url, filepath)
        print(f"  Downloaded pg{book_id}")
        return True
    except Exception as e:
        print(f"  Failed pg{book_id}: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100, help="Max books to fetch")
    args = parser.parse_args()

    RAW_DIR.mkdir(exist_ok=True)

    # Load existing books.json
    if BOOKS_JSON.exists():
        with open(BOOKS_JSON) as f:
            books = json.load(f)
    else:
        books = {}

    print(f"Fetching up to {args.count} books...")
    fetched = 0

    for book_id, title, author, era, topic, form, desc in BOOK_CATALOG:
        if fetched >= args.count:
            break

        # Skip verse for now
        if form == "verse":
            continue

        book_id_str = str(book_id)
        if book_id_str not in books:
            print(f"\n[{book_id}] {title}")
            if download_book(book_id):
                books[book_id_str] = {
                    "title": title,
                    "author": author,
                    "era": era,
                    "topic": topic,
                    "form": form,
                    "description": desc
                }
                fetched += 1
                time.sleep(1)  # Be nice to Gutenberg

    # Save updated books.json
    with open(BOOKS_JSON, "w") as f:
        json.dump(books, f, indent=2)

    print(f"\nDone. {len(books)} books in catalog.")


if __name__ == "__main__":
    main()
