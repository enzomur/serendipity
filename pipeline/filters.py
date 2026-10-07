"""
Quality filters for card chunks. Each predicate returns a reject reason string
if the chunk should be rejected, or None if it passes.

All thresholds are in FILTER_CONFIG, keyed by form (prose, sectioned).
"""

import re
from typing import Optional

# Thresholds tuned per text form. Sectioned texts (aphorisms, numbered sections)
# need relaxed thresholds since they're naturally shorter and may contain
# section numbers.
FILTER_CONFIG = {
    "prose": {
        "min_words": 80,
        "min_sentences": 2,
        "max_caps_ratio": 0.25,          # fraction of words that are ALL CAPS
        "max_title_case_ratio": 0.40,    # fraction of words in Title Case
        "max_digit_ratio": 0.08,         # digits + roman numerals / total chars
        "max_punct_ratio": 0.15,         # punctuation / total chars
        "max_bracket_ratio": 0.05,       # brackets / total chars
        "max_short_line_ratio": 0.30,    # lines under 40 chars / total lines
        "min_avg_line_length": 50,       # average chars per line
    },
    "sectioned": {
        "min_words": 12,                 # aphorisms can be short
        "min_sentences": 1,
        "max_caps_ratio": 0.30,
        "max_title_case_ratio": 0.50,
        "max_digit_ratio": 0.15,         # section numbers are fine
        "max_punct_ratio": 0.18,
        "max_bracket_ratio": 0.08,
        "max_short_line_ratio": 0.50,    # short lines more acceptable
        "min_avg_line_length": 30,
    },
}

# Patterns that strongly indicate junk content
TOC_PATTERNS = [
    r'(?i)^table of contents',
    r'(?i)^contents$',
    r'(?i)^chapter\s+[ivxlcdm\d]+\s*$',  # Chapter heading alone
    r'(?:\.{3,}|_{3,}|-{3,})\s*\d+',     # Dot/dash leaders to page numbers
    r'(?i)^index$',
    r'(?i)^appendix\s*[a-z]?\s*$',
]

FOOTNOTE_PATTERNS = [
    r'^\[\d+\]',                          # [1] style footnotes
    r'^\(\d+\)',                          # (1) style footnotes
    r'^\*{1,3}\s',                        # Asterisk footnotes
    r'(?i)^footnote',
    r'(?i)^endnote',
    r'(?i)^note\s*\d+',
    r'(?i)^\[editor',
    r'(?i)^\[translator',
]

FRONTMATTER_PATTERNS = [
    r'(?i)^produced by',
    r'(?i)^transcribed by',
    r'(?i)^scanned by',
    r'(?i)^e-?text prepared',
    r'(?i)^this e-?book',
    r'(?i)^project gutenberg',
    r'(?i)^distributed proofreaders',
    r'(?i)^online distributed',
    r'(?i)^illustration:?\s*$',
    r'(?i)^\[illustration',
    r'(?i)^copyright',
    r'(?i)^all rights reserved',
    r'(?i)^preface$',
    r'(?i)^introduction$',
    r'(?i)^translator.s note',
    r'(?i)^editor.s note',
    r'(?i)^publisher.s note',
    r'(?i)^advertisement$',
]

BIBLIOGRAPHY_PATTERNS = [
    r'(?i)^bibliography',
    r'(?i)^references$',
    r'(?i)^works cited',
    r'(?i)^see also:',
    r'(?i)^cf\.',
    r'(?i)^ibid\.',
    r'(?i)^op\.\s*cit\.',
    r'(?i)^loc\.\s*cit\.',
    r'(?i)^\d{4}\.\s+[A-Z]',             # Year + author pattern
]


def get_config(form: str) -> dict:
    """Get filter config for a text form, defaulting to prose."""
    return FILTER_CONFIG.get(form, FILTER_CONFIG["prose"])


def count_sentences(text: str) -> int:
    """Count sentences by terminal punctuation followed by space or end."""
    # Match . ! ? followed by space, newline, or end of string
    # Exclude common abbreviations
    cleaned = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|etc|al|ed|vol|ch)\.',
                     r'\1ABBR', text, flags=re.IGNORECASE)
    return len(re.findall(r'[.!?]+(?:\s|$)', cleaned))


def count_words(text: str) -> int:
    """Count words (sequences of word characters)."""
    return len(re.findall(r'\b\w+\b', text))


def is_roman_numeral(s: str) -> bool:
    """Check if string is a roman numeral."""
    return bool(re.fullmatch(r'[IVXLCDMivxlcdm]+', s))


# --- Individual filter predicates ---
# Each returns a reject reason string or None

def filter_too_short(text: str, form: str) -> Optional[str]:
    """Reject chunks below word floor."""
    config = get_config(form)
    word_count = count_words(text)
    if word_count < config["min_words"]:
        return f"too_short ({word_count} words, need {config['min_words']})"
    return None


def filter_few_sentences(text: str, form: str) -> Optional[str]:
    """Reject chunks without enough complete sentences."""
    config = get_config(form)
    sentence_count = count_sentences(text)
    if sentence_count < config["min_sentences"]:
        return f"few_sentences ({sentence_count}, need {config['min_sentences']})"
    return None


def filter_toc(text: str, form: str) -> Optional[str]:
    """Reject tables of contents and chapter lists."""
    lines = text.strip().split('\n')

    # Check first few lines for TOC indicators
    for line in lines[:5]:
        for pattern in TOC_PATTERNS:
            if re.search(pattern, line.strip()):
                return "toc_detected"

    # High density of dot leaders suggests TOC
    dot_leader_lines = sum(1 for line in lines if re.search(r'\.{3,}', line))
    if len(lines) > 3 and dot_leader_lines / len(lines) > 0.3:
        return "toc_dot_leaders"

    return None


def filter_footnotes(text: str, form: str) -> Optional[str]:
    """Reject footnote/endnote blocks."""
    lines = text.strip().split('\n')

    footnote_lines = 0
    for line in lines:
        stripped = line.strip()
        for pattern in FOOTNOTE_PATTERNS:
            if re.search(pattern, stripped):
                footnote_lines += 1
                break

    # If most lines look like footnotes, reject
    if len(lines) > 2 and footnote_lines / len(lines) > 0.4:
        return "footnote_block"

    # Single footnote reference at start
    if lines and re.match(r'^\[\d+\]', lines[0].strip()):
        return "footnote_start"

    return None


def filter_frontmatter(text: str, form: str) -> Optional[str]:
    """Reject transcriber notes, publisher info, etc."""
    lines = text.strip().split('\n')

    for line in lines[:3]:
        for pattern in FRONTMATTER_PATTERNS:
            if re.search(pattern, line.strip()):
                return "frontmatter"

    return None


def filter_bibliography(text: str, form: str) -> Optional[str]:
    """Reject bibliographies and citation runs."""
    lines = text.strip().split('\n')

    for line in lines[:3]:
        for pattern in BIBLIOGRAPHY_PATTERNS:
            if re.search(pattern, line.strip()):
                return "bibliography"

    return None


def filter_caps_heavy(text: str, form: str) -> Optional[str]:
    """Reject all-caps heavy text (headers, titles)."""
    config = get_config(form)
    words = re.findall(r'\b[A-Za-z]+\b', text)
    if not words:
        return "no_words"

    caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    ratio = caps_words / len(words)

    if ratio > config["max_caps_ratio"]:
        return f"caps_heavy ({ratio:.2f})"

    return None


def filter_title_case_heavy(text: str, form: str) -> Optional[str]:
    """Reject title-case heavy text (chapter lists, headings)."""
    config = get_config(form)
    words = re.findall(r'\b[A-Za-z]+\b', text)
    if not words:
        return None

    # Title case: first letter upper, rest lower, length > 1
    title_words = sum(1 for w in words
                      if len(w) > 1 and w[0].isupper() and w[1:].islower())

    # Discount words at sentence starts
    sentence_starts = len(re.findall(r'[.!?]\s+[A-Z]', text)) + 1
    adjusted = max(0, title_words - sentence_starts)

    ratio = adjusted / len(words) if words else 0

    if ratio > config["max_title_case_ratio"]:
        return f"title_case_heavy ({ratio:.2f})"

    return None


def filter_digit_heavy(text: str, form: str) -> Optional[str]:
    """Reject text with high digit/roman numeral density (page numbers, dates)."""
    config = get_config(form)

    if not text:
        return "empty"

    # Count digits
    digit_count = sum(1 for c in text if c.isdigit())

    # Count roman numerals in isolation
    roman_matches = re.findall(r'\b[IVXLCDMivxlcdm]+\b', text)
    roman_count = sum(len(m) for m in roman_matches if is_roman_numeral(m))

    total_chars = len(text.replace(' ', '').replace('\n', ''))
    if total_chars == 0:
        return "empty"

    ratio = (digit_count + roman_count) / total_chars

    if ratio > config["max_digit_ratio"]:
        return f"digit_heavy ({ratio:.2f})"

    return None


def filter_punct_heavy(text: str, form: str) -> Optional[str]:
    """Reject text with excessive punctuation (citation runs)."""
    config = get_config(form)

    punct_chars = sum(1 for c in text if c in '.,;:!?"\'-()[]{}')
    total_chars = len(text.replace(' ', '').replace('\n', ''))

    if total_chars == 0:
        return "empty"

    ratio = punct_chars / total_chars

    if ratio > config["max_punct_ratio"]:
        return f"punct_heavy ({ratio:.2f})"

    return None


def filter_bracket_heavy(text: str, form: str) -> Optional[str]:
    """Reject text with excessive brackets (editorial insertions)."""
    config = get_config(form)

    bracket_chars = sum(1 for c in text if c in '[](){}<>')
    total_chars = len(text.replace(' ', '').replace('\n', ''))

    if total_chars == 0:
        return "empty"

    ratio = bracket_chars / total_chars

    if ratio > config["max_bracket_ratio"]:
        return f"bracket_heavy ({ratio:.2f})"

    return None


def filter_short_lines(text: str, form: str) -> Optional[str]:
    """Reject text with many short lines (verse, lists, tables)."""
    config = get_config(form)

    lines = [l for l in text.split('\n') if l.strip()]
    if len(lines) < 3:
        return None  # Too few lines to judge

    short_lines = sum(1 for l in lines if len(l.strip()) < 40)
    ratio = short_lines / len(lines)

    if ratio > config["max_short_line_ratio"]:
        return f"short_lines ({ratio:.2f})"

    # Also check average line length
    avg_length = sum(len(l.strip()) for l in lines) / len(lines)
    if avg_length < config["min_avg_line_length"]:
        return f"avg_line_short ({avg_length:.0f} chars)"

    return None


def filter_chapter_heading_only(text: str, form: str) -> Optional[str]:
    """Reject chapter headings without body prose."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    if len(lines) <= 2:
        # Check if it's just a chapter/section heading
        combined = ' '.join(lines)
        if re.match(r'^(?:chapter|book|part|section)\s+[ivxlcdm\d]+',
                    combined, re.IGNORECASE):
            return "chapter_heading_only"

    return None


def filter_all_caps_block(text: str, form: str) -> Optional[str]:
    """Reject blocks that are entirely or mostly uppercase."""
    # Remove punctuation and whitespace for analysis
    letters = re.findall(r'[A-Za-z]', text)
    if len(letters) < 20:
        return None

    upper = sum(1 for c in letters if c.isupper())
    if upper / len(letters) > 0.7:
        return "all_caps_block"

    return None


# --- Main filter function ---

ALL_FILTERS = [
    filter_too_short,
    filter_few_sentences,
    filter_toc,
    filter_footnotes,
    filter_frontmatter,
    filter_bibliography,
    filter_caps_heavy,
    filter_title_case_heavy,
    filter_digit_heavy,
    filter_punct_heavy,
    filter_bracket_heavy,
    filter_short_lines,
    filter_chapter_heading_only,
    filter_all_caps_block,
]


def filter_chunk(text: str, form: str = "prose") -> Optional[str]:
    """
    Run all filters on a chunk. Returns first reject reason, or None if passes.
    """
    for f in ALL_FILTERS:
        reason = f(text, form)
        if reason:
            return reason
    return None


def filter_chunk_all_reasons(text: str, form: str = "prose") -> list[str]:
    """
    Run all filters and return all reject reasons (for diagnostics).
    """
    reasons = []
    for f in ALL_FILTERS:
        reason = f(text, form)
        if reason:
            reasons.append(reason)
    return reasons
