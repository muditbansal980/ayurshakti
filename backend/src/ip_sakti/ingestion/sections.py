"""Conservative legal boundary detection; uncertain material stays explicitly labelled."""

import re

NUMBER = r"[0-9०-९]+[A-Zअ-ह]?"
EXPLICIT = re.compile(rf"^(?:Section|SECTION|Rule|RULE|Article|ARTICLE|धारा|नियम|अनुच्छेद)\s+({NUMBER})\b")
NUMBERED = re.compile(rf"^(?:\d+\[|\[)?({NUMBER})(?:\s*\(1\))?\s*(?:\.\s*|(?=\s*\([1I]\s*\)))(.*)")
STRUCTURE = re.compile(r"^(?:CHAPTER|PART|अध्याय|भाग)\s+[IVXLC\d०-९]+\b", re.I)
SCHEDULE = re.compile(r"^(?:(?:THE|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+)*SCHEDULE(?:\s+[IVXLC\d]+)?[. ]*$|^अनुसूची(?:\s+[\d०-९]+)?$")
FOOTNOTE = re.compile(r"^(?:Ins\.|Subs\.|Cls?\.|Inserted|Omitted|Added|Substituted|G\.S\.R\.|S\.O\.|Vide|Came into force|Act \d+ of)", re.I)


def join_pages(pages: list[dict]) -> tuple[str, list[dict]]:
    text = ""
    spans = []
    for page in pages:
        start = len(text)
        text += page["text"] + "\n\n"
        spans.append({"page": page["page"], "start": start, "end": start + len(page["text"])})
    return text, spans


def pages_for_span(spans: list[dict], start: int, end: int) -> list[int]:
    return [p["page"] for p in spans if p["start"] < end and p["end"] > start]


def parse_sections(pages: list[dict], kind: str = "act") -> tuple[str, list[dict], list[str]]:
    text, spans = join_pages(pages)
    lines = list(re.finditer(r"[^\n]+", text))
    boundaries = []
    chapter = ""
    in_schedule = False
    body_started = False
    last_number = (0, "")
    # A table of contents lists titles without the enacting text. Skip it until
    # the repeated operative section 1; do not embed TOC entries as provisions.
    toc = False
    for index, match in enumerate(lines):
        line = match.group().strip()
        if "ARRANGEMENT OF SECTIONS" in line.upper() or "ARRANGEMENT OF RULES" in line.upper():
            toc = True
            continue
        if STRUCTURE.match(line):
            chapter = line
            continue
        if SCHEDULE.match(line) and body_started and not toc:
            boundaries.append((match.start(), line[:160], "schedule", chapter))
            in_schedule = True
            continue
        explicit = EXPLICIT.match(line)
        numbered = NUMBERED.match(line)
        number = explicit.group(1) if explicit else numbered.group(1) if numbered else None
        if not number:
            continue
        rest = line[explicit.end():] if explicit else numbered.group(2)
        if numbered and not explicit and not rest.strip():
            continue  # e.g. a wrapped year "1994.", not a provision heading
        if FOOTNOTE.match(rest.strip()):
            continue
        if explicit and re.match(r"\s*(?:[;,]|of\b|or\b|and\b|shall\b)", rest):
            continue
        context = " ".join(m.group().strip() for m in lines[index:index + 4])
        operative = bool(re.search(r"[.—–]\s*[—–-]|\.\s*-|\([1I]\s*\)|\b(?:This Act|These rules|In this Act|In these rules)\b", context))
        if not body_started and (number not in ("1", "१") or not (operative or explicit)):
            continue
        if toc:
            if number not in ("1", "१") or not operative:
                continue
            toc = False
        if in_schedule:
            # Numbered rows/forms in a schedule are not new statutory sections.
            continue
        if not explicit and not operative and not re.match(r"\[?[A-Z\u0900-\u097f]", rest):
            continue
        numeric = re.match(r"([0-9०-९]+)(.*)", number)
        key = (int(numeric.group(1)), numeric.group(2))
        if key <= last_number:
            # Footnotes and wrapped cross-references often begin with numbers.
            # Preserve their text inside the current parent rather than making
            # a misleading new statutory provision.
            continue
        last_number = key
        body_started = True
        label = "Article" if kind == "treaty" else "Rule" if kind == "rules" else "Section"
        boundaries.append((match.start(), f"{label} {number}", "provision", chapter))
    warnings = []
    if in_schedule:
        warnings.append("Schedule/table layout requires review against the original PDF.")
    if not boundaries:
        warnings.append("No reliable section boundaries detected; page-level fallback requires review.")
        sections = [
            {"locator": f"PDF page {p['page']}", "kind": "page_fallback", "chapter": "",
             "start": p["start"], "end": p["end"], "pages": [p["page"]],
             "text": text[p["start"]:p["end"]]}
            for p in spans if text[p["start"]:p["end"]].strip()
        ]
        return text, sections, warnings
    sections = []
    # Material preceding the operative text is retained in extraction output but
    # excluded from the retrieval index (covers, contents, preamble).
    for i, (start, locator, section_kind, heading) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        sections.append({"locator": locator, "kind": section_kind, "chapter": heading,
                         "start": start, "end": end, "pages": pages_for_span(spans, start, end),
                         "text": text[start:end]})
    labels = [s["locator"] for s in sections if s["kind"] == "provision"]
    if len(labels) != len(set(labels)):
        warnings.append("Repeated provision numbers detected; inspect extraction/footnotes before verification.")
    return text, sections, warnings

