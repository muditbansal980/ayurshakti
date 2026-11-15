import hashlib
import re

from ip_sakti.ingestion.sections import join_pages, pages_for_span

PIPELINE_VERSION = "section-parent-child-v1"


def stable_id(*values: object) -> str:
    return hashlib.sha256("\x1f".join(str(v) for v in values).encode()).hexdigest()


def build_chunks(document: dict, pages: list[dict], sections: list[dict], tokenizer,
                 *, target_tokens: int = 384, overlap_tokens: int = 32) -> tuple[list[dict], list[dict]]:
    if not 128 <= target_tokens <= 480 or not 0 <= overlap_tokens < target_tokens // 3:
        raise ValueError("Use 128–480 tokens and overlap smaller than one third of target.")
    _, spans = join_pages(pages)
    parents, children = [], []
    for section in sections:
        parent_id = stable_id(document["sha256"], section["start"], section["end"], PIPELINE_VERSION)
        parent = {**section, "_id": parent_id, "document_id": document["sha256"]}
        parents.append(parent)
        # Keep titles short enough to leave room for actual evidence.
        title = document["title"][:200]
        header = f"passage: {title} | {section['locator']}\n"
        header_size = len(tokenizer.encode(header, add_special_tokens=True))
        budget = target_tokens - header_size - 8
        if budget < 32:
            raise ValueError("Document title/locator leaves insufficient embedding space.")
        text = section["text"]
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                            truncation=False, verbose=False)["offset_mapping"]
        cursor = 0
        while cursor < len(offsets):
            last = min(cursor + budget, len(offsets))
            start = offsets[cursor][0]
            end = offsets[last - 1][1]
            if last < len(offsets):
                candidates = list(re.finditer(r"\n(?=\(\d+\)|\([a-z]+\)|Provided|Explanation)|(?<=[.!?।])\s+", text[start:end]))
                if candidates and candidates[-1].end() > (end - start) // 2:
                    end = start + candidates[-1].end()
                    while last > cursor + 1 and offsets[last - 1][1] > end:
                        last -= 1
                    end = offsets[last - 1][1]
            # Some tokenizers map multiple Unicode sub-tokens to one character.
            # Recount the exact input and shrink rather than trusting estimates.
            while len(tokenizer.encode(header + text[start:end], add_special_tokens=True)) > target_tokens:
                last -= 1
                if last <= cursor:
                    raise ValueError("Unable to fit a child within the token budget.")
                end = offsets[last - 1][1]
            absolute_start, absolute_end = section["start"] + start, section["start"] + end
            child = {
                "_id": stable_id(parent_id, start, end, target_tokens, overlap_tokens),
                "document_id": document["sha256"], "parent_id": parent_id,
                "locator": section["locator"], "text": text[start:end],
                "embedding_text": header + text[start:end],
                "start": absolute_start, "end": absolute_end,
                "pages": pages_for_span(spans, absolute_start, absolute_end),
                "token_count": len(tokenizer.encode(header + text[start:end], add_special_tokens=True)),
            }
            children.append(child)
            if last == len(offsets):
                break
            cursor = max(cursor + 1, last - overlap_tokens)
    return parents, children
