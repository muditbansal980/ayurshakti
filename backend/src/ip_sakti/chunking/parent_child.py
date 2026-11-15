
import hashlib
import re
from typing import Any

from ip_sakti.ingestion.sections import join_pages, pages_for_span


PIPELINE_VERSION = "section-parent-child-v1"

LEGAL_BOUNDARY_PATTERN = re.compile(
    r"\n(?=\(\d+\)|\([a-z]+\)|Provided|Explanation)"
    r"|(?<=[.!?।])\s+"
)

MIN_CHUNK_TOKENS = 128
MAX_CHUNK_TOKENS = 480
MIN_TEXT_BUDGET = 32
HEADER_SAFETY_MARGIN = 8

# Generates a deterministic unique ID from the provided values.
def stable_id(*values: object) -> str:
    """Generate a deterministic SHA-256 ID from multiple values."""
    raw_value = "\x1f".join(str(value) for value in values)
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()

# Validates the child chunk size and overlap configuration.
def validate_chunk_settings(
    target_tokens: int,
    overlap_tokens: int,
) -> None:
    """Validate chunk size and overlap configuration."""

    if not MIN_CHUNK_TOKENS <= target_tokens <= MAX_CHUNK_TOKENS:
        raise ValueError("Target tokens must be between 128 and 480.")

    if not 0 <= overlap_tokens < target_tokens // 3:
        raise ValueError(
            "Overlap must be non-negative and smaller than one-third "
            "of the target token count."
        )

# Creates a parent record representing the complete legal section.
def create_parent_record(
    document: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    """Create a complete parent record for a legal section."""

    parent_id = stable_id(
        document["sha256"],
        section["start"],
        section["end"],
        PIPELINE_VERSION,
    )

    return {
        **section,
        "_id": parent_id,
        "document_id": document["sha256"],
    }

# Builds the context header used while generating embeddings.
def build_embedding_header(
    document: dict[str, Any],
    section: dict[str, Any],
) -> str:
    """Add document and section context before embedding."""

    document_title = document["title"][:200]
    section_locator = section["locator"]

    return f"passage: {document_title} | {section_locator}\n"

# Returns the number of tokens in the given text.
def count_tokens(text: str, tokenizer: Any) -> int:
    """Count tokens including special tokens."""

    return len(
        tokenizer.encode(
            text,
            add_special_tokens=True,
        )
    )

# Finds a suitable sentence or legal-structure boundary for splitting.
def find_chunk_boundary(
    text: str,
    start: int,
    end: int,
) -> int:
    """
    Find a natural sentence or legal-structure boundary.

    Only consider boundaries in the latter half of the chunk
    to avoid unnecessarily small chunks.
    """

    candidates = list(
        LEGAL_BOUNDARY_PATTERN.finditer(text[start:end])
    )

    if not candidates:
        return end

    last_boundary = candidates[-1].end()

    if last_boundary <= (end - start) // 2:
        return end

    return start + last_boundary

# Extracts token-level character offsets from the section text.
def get_token_offsets(
    text: str,
    tokenizer: Any,
) -> list[tuple[int, int]]:
    """Get character offsets for every token in the section."""

    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        truncation=False,
        verbose=False,
    )

    return encoded["offset_mapping"]

# Adjusts a chunk so its embedding text stays within the token budget.
def fit_chunk_within_budget(
    header: str,
    text: str,
    token_offsets: list[tuple[int, int]],
    cursor: int,
    last_token: int,
    target_tokens: int,
    tokenizer: Any,
) -> tuple[int, int]:
    """
    Adjust the chunk end until header + text fits
    within the exact token limit.

    Returns:
        Updated last token index and character end offset.
    """

    chunk_start = token_offsets[cursor][0]
    chunk_end = token_offsets[last_token - 1][1]

    while count_tokens(
        header + text[chunk_start:chunk_end],
        tokenizer,
    ) > target_tokens:

        last_token -= 1

        if last_token <= cursor:
            raise ValueError(
                "Unable to fit a child within the token budget."
            )

        chunk_end = token_offsets[last_token - 1][1]

    return last_token, chunk_end

# Creates a child chunk with its text, metadata, and parent reference.
def create_child_record(
    document: dict[str, Any],
    section: dict[str, Any],
    parent_id: str,
    header: str,
    text: str,
    chunk_start: int,
    chunk_end: int,
    absolute_start: int,
    absolute_end: int,
    page_spans: list[dict[str, Any]],
    target_tokens: int,
    overlap_tokens: int,
    tokenizer: Any,
) -> dict[str, Any]:
    """Create a searchable child chunk with citation metadata."""

    embedding_text = header + text[chunk_start:chunk_end]

    return {
        "_id": stable_id(
            parent_id,
            chunk_start,
            chunk_end,
            target_tokens,
            overlap_tokens,
        ),
        "document_id": document["sha256"],
        "parent_id": parent_id,
        "locator": section["locator"],
        "text": text[chunk_start:chunk_end],
        "embedding_text": embedding_text,
        "start": absolute_start,
        "end": absolute_end,
        "pages": pages_for_span(
            page_spans,
            absolute_start,
            absolute_end,
        ),
        "token_count": count_tokens(
            embedding_text,
            tokenizer,
        ),
    }

# Splits a legal section into smaller overlapping child chunks.
def create_child_chunks(
    document: dict[str, Any],
    section: dict[str, Any],
    parent_id: str,
    page_spans: list[dict[str, Any]],
    tokenizer: Any,
    target_tokens: int,
    overlap_tokens: int,
) -> list[dict[str, Any]]:
    """Split one legal section into overlapping child chunks."""

    section_text = section["text"]

    if not section_text.strip():
        return []

    header = build_embedding_header(document, section)

    header_tokens = count_tokens(header, tokenizer)

    text_budget = (
        target_tokens
        - header_tokens
        - HEADER_SAFETY_MARGIN
    )

    if text_budget < MIN_TEXT_BUDGET:
        raise ValueError(
            "Document title and section locator leave "
            "insufficient space for legal text."
        )

    token_offsets = get_token_offsets(section_text, tokenizer)

    if not token_offsets:
        return []

    children = []
    cursor = 0

    while cursor < len(token_offsets):

        last_token = min(
            cursor + text_budget,
            len(token_offsets),
        )

        chunk_start = token_offsets[cursor][0]
        chunk_end = token_offsets[last_token - 1][1]

        # Prefer natural sentence or legal boundaries.
        if last_token < len(token_offsets):
            chunk_end = find_chunk_boundary(
                section_text,
                chunk_start,
                chunk_end,
            )

            # Move the token boundary to the selected character boundary.
            while (
                last_token > cursor + 1
                and token_offsets[last_token - 1][1] > chunk_end
            ):
                last_token -= 1

            chunk_end = token_offsets[last_token - 1][1]

        # Guarantee that the final embedding input fits the token limit.
        last_token, chunk_end = fit_chunk_within_budget(
            header=header,
            text=section_text,
            token_offsets=token_offsets,
            cursor=cursor,
            last_token=last_token,
            target_tokens=target_tokens,
            tokenizer=tokenizer,
        )

        absolute_start = section["start"] + chunk_start
        absolute_end = section["start"] + chunk_end

        child = create_child_record(
            document=document,
            section=section,
            parent_id=parent_id,
            header=header,
            text=section_text,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            absolute_start=absolute_start,
            absolute_end=absolute_end,
            page_spans=page_spans,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
            tokenizer=tokenizer,
        )

        children.append(child)

        # Stop when the complete section has been processed.
        if last_token == len(token_offsets):
            break

        # Move backwards to preserve overlap with the next chunk.
        cursor = max(
            cursor + 1,
            last_token - overlap_tokens,
        )

    return children

# Builds all parent and child records for the document.
def build_chunks(
    document: dict[str, Any],
    pages: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    tokenizer: Any,
    *,
    target_tokens: int = 384,
    overlap_tokens: int = 32,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Build parent and child records from structured legal sections.

    Parents:
        Complete legal sections.

    Children:
        Smaller, overlapping, searchable chunks with citation metadata.
    """

    validate_chunk_settings(
        target_tokens,
        overlap_tokens,
    )

    _, page_spans = join_pages(pages)

    parents = []
    children = []

    for section in sections:

        parent = create_parent_record(
            document,
            section,
        )

        parents.append(parent)

        section_children = create_child_chunks(
            document=document,
            section=section,
            parent_id=parent["_id"],
            page_spans=page_spans,
            tokenizer=tokenizer,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )

        children.extend(section_children)

    return parents, children
