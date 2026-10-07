"""
Text cleaning and chunking for Gutenberg texts.

Handles two forms:
- prose: unwrap hard-wrapped lines, chunk by word count on paragraph boundaries
- sectioned: chunk on section/aphorism boundaries, one section per card
"""

import re
import hashlib
from dataclasses import dataclass
from typing import Iterator, Optional

# Chunking parameters
PROSE_TARGET_WORDS = 300
PROSE_MIN_WORDS = 150
PROSE_MAX_WORDS = 500

SECTIONED_MIN_WORDS = 15  # Allow short aphorisms
SECTIONED_MERGE_THRESHOLD = 30  # Merge consecutive sections below this


@dataclass
class Chunk:
    """A card-ready text chunk with metadata."""
    text: str
    char_offset: int      # Offset in cleaned text (for stable ID)
    section_num: Optional[str] = None  # For sectioned texts


def extract_body(raw_text: str) -> str:
    """
    Strip Gutenberg header/footer, keeping only the actual book content.
    Returns text between START and END markers.
    """
    # Find start marker (various formats exist)
    start_patterns = [
        r'\*\*\*\s*START OF TH(?:IS|E) PROJECT GUTENBERG EBOOK[^*]*\*\*\*',
        r'\*\*\*\s*START OF THE PROJECT GUTENBERG[^*]*\*\*\*',
        r'\*{3,}\s*START[^*]*\*{3,}',
    ]

    start_pos = 0
    for pattern in start_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            start_pos = match.end()
            break

    # Find end marker
    end_patterns = [
        r'\*\*\*\s*END OF TH(?:IS|E) PROJECT GUTENBERG EBOOK[^*]*\*\*\*',
        r'\*\*\*\s*END OF THE PROJECT GUTENBERG[^*]*\*\*\*',
        r'\*{3,}\s*END[^*]*\*{3,}',
        r'End of (?:the )?Project Gutenberg',
    ]

    end_pos = len(raw_text)
    for pattern in end_patterns:
        match = re.search(pattern, raw_text[start_pos:], re.IGNORECASE)
        if match:
            end_pos = start_pos + match.start()
            break

    return raw_text[start_pos:end_pos].strip()


def clean_prose(text: str) -> str:
    """
    Clean prose text: unwrap hard-wrapped lines, normalize whitespace.

    Gutenberg texts are hard-wrapped at ~70 chars. We need to:
    1. Join lines within paragraphs (line ends without blank line after)
    2. Preserve paragraph breaks (blank lines)
    3. Strip transcriber/illustration notes
    """
    # Remove illustration markers
    text = re.sub(r'\[Illustration[^\]]*\]', '', text, flags=re.IGNORECASE)

    # Remove transcriber notes in brackets
    text = re.sub(r'\[Transcriber.s [^\]]+\]', '', text, flags=re.IGNORECASE)

    # Remove "Produced by" blocks (usually at very start)
    text = re.sub(r'^Produced by[^\n]*\n(?:[^\n]*\n)*?\n',
                  '', text, flags=re.IGNORECASE)

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Split into paragraphs (separated by blank lines)
    # A blank line is one or more consecutive \n\n
    paragraphs = re.split(r'\n\s*\n', text)

    cleaned_paragraphs = []
    for para in paragraphs:
        # Skip empty paragraphs
        if not para.strip():
            continue

        # Unwrap hard-wrapped lines within this paragraph
        # Join lines that don't end with sentence-terminal punctuation
        lines = para.split('\n')
        unwrapped = []
        buffer = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            buffer.append(line)

            # If line ends with sentence-terminal punctuation or is very short
            # (like a heading), it might be a natural break. But for hard-wrap
            # detection, we mostly just join everything.

        if buffer:
            # Join all lines in the paragraph with spaces
            joined = ' '.join(buffer)
            # Normalize multiple spaces
            joined = re.sub(r' +', ' ', joined)
            cleaned_paragraphs.append(joined)

    return '\n\n'.join(cleaned_paragraphs)


def clean_sectioned(text: str) -> str:
    """
    Clean sectioned text: preserve section structure, light cleanup.

    Unlike prose, we don't aggressively unwrap since section formatting
    may be meaningful.
    """
    # Remove illustration markers
    text = re.sub(r'\[Illustration[^\]]*\]', '', text, flags=re.IGNORECASE)

    # Remove transcriber notes
    text = re.sub(r'\[Transcriber.s [^\]]+\]', '', text, flags=re.IGNORECASE)

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Normalize multiple blank lines to double
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Normalize spaces
    text = re.sub(r' +', ' ', text)

    return text.strip()


def split_sections(text: str) -> list[tuple[str, str, int]]:
    """
    Split sectioned text into (section_number, section_text, char_offset) tuples.

    Handles various section marker formats:
    - Roman numerals standalone: "IV." on its own line
    - Roman numerals inline: "IV. Of my grandfather..."
    - Arabic numerals: "1." or "42."
    - Prefixed: "Book I", "Chapter 1", etc.
    """
    # Pattern for standalone section markers (number alone on line)
    standalone_pattern = re.compile(
        r'^([IVXLCDM]+|\d+)\.?\s*$',
        re.IGNORECASE
    )

    # Pattern for inline section markers: "IV. Text..." at line start
    # Must have period and space, then actual content
    inline_pattern = re.compile(
        r'^([IVXLCDM]+|\d+)\.\s+(.+)',
        re.IGNORECASE
    )

    # Pattern for prefixed sections: "Book I", "Chapter 1"
    prefixed_pattern = re.compile(
        r'^(?:Section|Chapter|Book)\s+([IVXLCDM\d]+)',
        re.IGNORECASE
    )

    sections = []
    lines = text.split('\n')

    current_section_num = None
    current_section_lines = []
    section_start_offset = 0

    char_pos = 0
    for line in lines:
        line_start = char_pos
        stripped = line.strip()

        section_num = None
        remaining_text = None

        # Check for standalone section marker
        match = standalone_pattern.match(stripped)
        if match:
            section_num = match.group(1).upper()
        else:
            # Check for inline section marker
            match = inline_pattern.match(stripped)
            if match:
                section_num = match.group(1).upper()
                remaining_text = match.group(2)
            else:
                # Check for prefixed section
                match = prefixed_pattern.match(stripped)
                if match:
                    section_num = match.group(1).upper()

        if section_num is not None:
            # Save previous section if any
            if current_section_lines:
                section_text = '\n'.join(current_section_lines).strip()
                if section_text:
                    sections.append((current_section_num or "", section_text,
                                     section_start_offset))

            current_section_num = section_num
            current_section_lines = []
            section_start_offset = line_start

            # If inline, include the remaining text
            if remaining_text:
                current_section_lines.append(remaining_text)
        else:
            current_section_lines.append(line)

        char_pos += len(line) + 1  # +1 for newline

    # Don't forget last section
    if current_section_lines:
        section_text = '\n'.join(current_section_lines).strip()
        if section_text:
            sections.append((current_section_num or "", section_text,
                             section_start_offset))

    # If no sections found, treat whole text as one section
    if not sections:
        sections = [("", text.strip(), 0)]

    return sections


def chunk_prose(text: str) -> Iterator[Chunk]:
    """
    Chunk prose text by accumulating paragraphs to target word count.

    Rules:
    - Never split mid-paragraph
    - Target ~300 words, min 150, max 500
    - End on sentence-terminal punctuation
    """
    paragraphs = text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    current_chunk = []
    current_words = 0
    chunk_start_offset = 0

    char_pos = 0
    for para in paragraphs:
        para_words = len(re.findall(r'\b\w+\b', para))

        # If adding this paragraph exceeds max and we have enough, emit
        if current_words + para_words > PROSE_MAX_WORDS and current_words >= PROSE_MIN_WORDS:
            chunk_text = '\n\n'.join(current_chunk)
            yield Chunk(text=chunk_text, char_offset=chunk_start_offset)

            current_chunk = [para]
            current_words = para_words
            chunk_start_offset = char_pos
        else:
            if not current_chunk:
                chunk_start_offset = char_pos
            current_chunk.append(para)
            current_words += para_words

        char_pos += len(para) + 2  # +2 for paragraph separator

    # Emit remaining
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        yield Chunk(text=chunk_text, char_offset=chunk_start_offset)


def chunk_sectioned(text: str) -> Iterator[Chunk]:
    """
    Chunk sectioned text: one section per card, merging very short ones.
    """
    sections = split_sections(text)

    # Post-process: merge very short consecutive sections
    merged = []
    buffer_sections = []
    buffer_words = 0
    buffer_offset = 0

    for section_num, section_text, offset in sections:
        word_count = len(re.findall(r'\b\w+\b', section_text))

        if word_count < SECTIONED_MERGE_THRESHOLD:
            if not buffer_sections:
                buffer_offset = offset
            buffer_sections.append((section_num, section_text))
            buffer_words += word_count
        else:
            # Flush buffer if any
            if buffer_sections:
                combined_text = '\n\n'.join(s[1] for s in buffer_sections)
                combined_num = buffer_sections[0][0]
                if len(buffer_sections) > 1:
                    combined_num = f"{buffer_sections[0][0]}-{buffer_sections[-1][0]}"
                merged.append((combined_num, combined_text, buffer_offset))
                buffer_sections = []
                buffer_words = 0

            merged.append((section_num, section_text, offset))

    # Final flush
    if buffer_sections:
        combined_text = '\n\n'.join(s[1] for s in buffer_sections)
        combined_num = buffer_sections[0][0]
        if len(buffer_sections) > 1:
            combined_num = f"{buffer_sections[0][0]}-{buffer_sections[-1][0]}"
        merged.append((combined_num, combined_text, buffer_offset))

    for section_num, section_text, offset in merged:
        # Clean up the section text for card display
        # Unwrap hard-wrapped lines within the section
        lines = section_text.split('\n')
        cleaned_lines = []
        buffer = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if buffer:
                    cleaned_lines.append(' '.join(buffer))
                    buffer = []
                cleaned_lines.append('')
            else:
                buffer.append(stripped)

        if buffer:
            cleaned_lines.append(' '.join(buffer))

        cleaned_text = '\n'.join(cleaned_lines).strip()
        # Normalize multiple newlines
        cleaned_text = re.sub(r'\n{2,}', '\n\n', cleaned_text)

        yield Chunk(
            text=cleaned_text,
            char_offset=offset,
            section_num=section_num
        )


def generate_card_id(gutenberg_id: str, char_offset: int) -> str:
    """
    Generate stable card ID from source + offset.
    Uses first 12 chars of SHA-256 for uniqueness without bloat.
    """
    key = f"{gutenberg_id}:{char_offset}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def process_text(raw_text: str, form: str, gutenberg_id: str) -> Iterator[Chunk]:
    """
    Main entry point: clean and chunk text according to form.
    """
    # Extract body (strip Gutenberg header/footer)
    body = extract_body(raw_text)

    if form == "prose":
        cleaned = clean_prose(body)
        yield from chunk_prose(cleaned)
    elif form == "sectioned":
        cleaned = clean_sectioned(body)
        yield from chunk_sectioned(cleaned)
    elif form == "verse":
        # v1: skip verse, handled by caller
        return
    else:
        # Unknown form, try prose
        cleaned = clean_prose(body)
        yield from chunk_prose(cleaned)
