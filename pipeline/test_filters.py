"""
Tests for filter predicates. Run with: python -m pytest test_filters.py -v
Or without pytest: python test_filters.py
"""

import unittest
from filters import (
    filter_chunk, filter_too_short, filter_few_sentences, filter_toc,
    filter_footnotes, filter_frontmatter, filter_bibliography,
    filter_caps_heavy, filter_title_case_heavy, filter_digit_heavy,
    filter_punct_heavy, filter_bracket_heavy, filter_short_lines,
    filter_chapter_heading_only, filter_all_caps_block
)


# --- Test fixtures: real examples of content types ---

# Good prose passage (should pass)
GOOD_PROSE = """
The longest way round is the shortest way home. We shall never know the
reason of anything until we have discovered why there is anything at all.
Philosophy begins in wonder. And, at the end, when philosophic thought has
done its best, the wonder remains. There have been added, however, some
grasp of the immensity of things, some purification of emotion by
understanding.

The value of philosophy is, in fact, to be sought largely in its very
uncertainty. The man who has no tincture of philosophy goes through life
imprisoned in the prejudices derived from common sense, from the habitual
beliefs of his age or his nation, and from convictions which have grown up
in his mind without the cooperation or consent of his deliberate reason.
"""

# Good sectioned passage - Marcus Aurelius style (should pass with sectioned form)
GOOD_SECTIONED = """
Never value anything as profitable that compels you to break your promise,
lose your self-respect, hate any man, suspect, curse, act the hypocrite,
or desire anything that needs walls or curtains.
"""

GOOD_SECTIONED_LONGER = """
Begin the morning by saying to yourself, I shall meet with the busybody,
the ungrateful, arrogant, deceitful, envious, unsocial. All these things
happen to them by reason of their ignorance of what is good and evil. But
I who have seen the nature of the good that it is beautiful, and of the
bad that it is ugly, and the nature of him who does wrong, that it is
akin to me; not only of the same blood or seed, but that it participates
in the same intelligence and the same portion of the divinity, I can
neither be injured by any of them, for no one can fix on me what is ugly,
nor can I be angry with my kinsman, nor hate him.
"""

# Table of contents (should be rejected)
TOC_FIXTURE = """
CONTENTS

Chapter I. The Early Years.......................... 1
Chapter II. The Journey Begins..................... 23
Chapter III. Trials and Tribulations............... 45
Chapter IV. The Final Victory...................... 89
Index.............................................. 112
"""

# Footnote block (should be rejected)
FOOTNOTE_FIXTURE = """
[1] See the commentary in Smith's edition, vol. II, p. 234.

[2] This passage is disputed. Compare with the variant reading
in the Oxford manuscript.

[3] The translator has rendered this phrase literally, though
the idiomatic meaning differs considerably.

[4] Op. cit., p. 156.
"""

# Frontmatter (should be rejected)
FRONTMATTER_FIXTURE = """
Produced by John Smith and the Online Distributed
Proofreading Team at http://www.pgdp.net

This e-book is for the use of anyone anywhere at no cost
and with almost no restrictions whatsoever.

TRANSLATOR'S NOTE

This translation was made from the third German edition,
and represents the most complete version of the text.
"""

# Chapter heading only (should be rejected)
CHAPTER_HEADING = """
CHAPTER IV

THE NATURE OF MATTER
"""

# All caps block (should be rejected)
ALL_CAPS = """
THIS ENTIRE PASSAGE IS WRITTEN IN CAPITAL LETTERS WHICH
MAKES IT VERY DIFFICULT TO READ AND USUALLY INDICATES
THAT IT IS A TITLE OR HEADER RATHER THAN ACTUAL CONTENT
THAT WOULD BE VALUABLE FOR A READING CARD.
"""

# Bibliography (should be rejected)
BIBLIOGRAPHY_FIXTURE = """
BIBLIOGRAPHY

1923. Smith, J. The Philosophy of Mind. Oxford University Press.
1925. Jones, A. Metaphysics Revisited. Cambridge.
1927. Brown, R. Essays on Being. London: Methuen.
1930. Williams, T. The Nature of Truth. Harvard University Press.
"""

# High digit ratio (should be rejected as prose, may pass as sectioned)
DIGIT_HEAVY = """
In 1845, the population reached 2,340,000. By 1850 it had grown
to 2,890,000, and in 1855 the census recorded 3,450,000. The
years 1860-1865 saw an increase of 15%, while 1870 showed 4,230,000.
Page references: 12, 34, 56, 78, 90, 112, 134, 156.
"""

# Verse-like short lines (should be rejected)
SHORT_LINES = """
The rose
blooms red
in spring.

The bird
sings sweet
at dawn.

The wind
blows soft
through leaves.
"""


class TestFilters(unittest.TestCase):
    """Test individual filter predicates."""

    def test_good_prose_passes(self):
        """Good prose should pass all filters."""
        result = filter_chunk(GOOD_PROSE, "prose")
        self.assertIsNone(result, f"Good prose rejected: {result}")

    def test_good_sectioned_passes(self):
        """Good sectioned content should pass with sectioned thresholds."""
        result = filter_chunk(GOOD_SECTIONED, "sectioned")
        self.assertIsNone(result, f"Good sectioned rejected: {result}")

        result = filter_chunk(GOOD_SECTIONED_LONGER, "sectioned")
        self.assertIsNone(result, f"Good sectioned longer rejected: {result}")

    def test_toc_rejected(self):
        """Table of contents should be rejected."""
        result = filter_toc(TOC_FIXTURE, "prose")
        self.assertIsNotNone(result)
        self.assertIn("toc", result.lower())

    def test_footnotes_rejected(self):
        """Footnote blocks should be rejected."""
        result = filter_footnotes(FOOTNOTE_FIXTURE, "prose")
        self.assertIsNotNone(result)
        self.assertIn("footnote", result.lower())

    def test_frontmatter_rejected(self):
        """Frontmatter/transcriber notes should be rejected."""
        result = filter_frontmatter(FRONTMATTER_FIXTURE, "prose")
        self.assertIsNotNone(result)
        self.assertIn("frontmatter", result.lower())

    def test_bibliography_rejected(self):
        """Bibliography should be rejected."""
        result = filter_bibliography(BIBLIOGRAPHY_FIXTURE, "prose")
        self.assertIsNotNone(result)

    def test_chapter_heading_rejected(self):
        """Chapter headings without body should be rejected."""
        # This may be caught by too_short or chapter_heading_only
        result = filter_chunk(CHAPTER_HEADING, "prose")
        self.assertIsNotNone(result)

    def test_all_caps_rejected(self):
        """All-caps blocks should be rejected."""
        result = filter_all_caps_block(ALL_CAPS, "prose")
        self.assertIsNotNone(result)

    def test_digit_heavy_prose_rejected(self):
        """High digit density should be rejected in prose."""
        result = filter_digit_heavy(DIGIT_HEAVY, "prose")
        self.assertIsNotNone(result)

    def test_short_lines_rejected(self):
        """Verse-like short lines should be rejected."""
        result = filter_short_lines(SHORT_LINES, "prose")
        self.assertIsNotNone(result)

    def test_sectioned_short_allowed(self):
        """Short aphorisms should pass sectioned filters."""
        short_aphorism = "Waste no more time arguing about what a good man should be. Be one."
        # This is very short but should pass sectioned
        result = filter_too_short(short_aphorism, "sectioned")
        self.assertIsNone(result, f"Short aphorism rejected: {result}")

    def test_sectioned_digits_relaxed(self):
        """Section numbers should not trigger digit filter in sectioned mode."""
        with_section_num = """
        IV. The soul of man is immortal and imperishable. It neither
        comes into being nor does it ever cease to be, nor having
        been will it ever not be. Unborn, eternal, everlasting, this
        ancient soul is not slain when the body is slain.
        """
        result = filter_digit_heavy(with_section_num, "sectioned")
        self.assertIsNone(result, f"Sectioned with number rejected: {result}")


class TestFilterIntegration(unittest.TestCase):
    """Test filter_chunk integration."""

    def test_prose_integration(self):
        """Prose content routed correctly."""
        self.assertIsNone(filter_chunk(GOOD_PROSE, "prose"))
        self.assertIsNotNone(filter_chunk(TOC_FIXTURE, "prose"))
        self.assertIsNotNone(filter_chunk(FOOTNOTE_FIXTURE, "prose"))

    def test_sectioned_integration(self):
        """Sectioned content with relaxed thresholds."""
        # Should pass
        self.assertIsNone(filter_chunk(GOOD_SECTIONED_LONGER, "sectioned"))

        # TOC should still fail
        self.assertIsNotNone(filter_chunk(TOC_FIXTURE, "sectioned"))


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
