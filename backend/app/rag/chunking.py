"""Deterministic local chunking without model tokenizers or network access."""

import hashlib
import json
import re

from app.rag.ingest import Document

# Four-character word pieces and punctuation are a reproducible token estimate,
# not a model-specific tokenizer. Offsets retain original text and formatting.
TOKEN = re.compile(r'\w{1,4}|[^\w\s]', re.UNICODE)
HEADING = re.compile(r'^(?:#{1,6}\s+.+|[A-Z][A-Z\s\d:–-]{2,})$', re.MULTILINE)


def approximate_token_count(text: str) -> int:
    return len(TOKEN.findall(text))


def word_windows(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """Whole-whitespace-delimited words; an indivisible oversized word stays intact."""
    words = list(re.finditer(r'\S+', text))
    weights = [approximate_token_count(word.group()) for word in words]
    windows = []
    start = 0
    while start < len(words):
        end, used = start, 0
        while end < len(words) and (used + weights[end] <= size or end == start):
            used += weights[end]
            end += 1
        windows.append((words[start].start(), words[end - 1].end()))
        if end == len(words):
            break
        next_start, carried = end, 0
        while next_start > start + 1 and carried + weights[next_start-1] <= overlap:
            next_start -= 1
            carried += weights[next_start]
        start = next_start
    return windows


def _fixed(text: str, size: int, overlap: int) -> list[str]:
    return [text[a:b] for a, b in word_windows(text, size, overlap)]


def _structure(text: str, size: int, overlap: int) -> list[str]:
    # Keep each heading and its following paragraphs/instructions together.
    # Pack whole sections when possible; oversized sections fall back to windows.
    boundaries = sorted({0, *(match.start() for match in HEADING.finditer(text)), len(text)})
    sections = [text[a:b].strip() for a, b in zip(boundaries, boundaries[1:])]
    chunks = []
    pending = ''
    for section in filter(None, sections):
        if approximate_token_count(section) > size:
            blocks = re.split(r'\n\s*\n', section)
        else:
            blocks = [section]
        for block in blocks:
            candidate = '\n\n'.join(filter(None, (pending, block)))
            if approximate_token_count(candidate) <= size:
                pending = candidate
                continue
            if pending:
                chunks.append(pending)
                pending = ''
            if approximate_token_count(block) > size:
                chunks.extend(_fixed(block, size, overlap))
            else:
                pending = block
    if pending:
        chunks.append(pending)
    return chunks


def chunk_documents(documents: list[Document], strategy: str = 'fixed',
                    chunk_size: int = 500, overlap: int = 75) -> list[Document]:
    """Copy document metadata; IDs include content, settings, and position.

    Structure chunks overlap only when an oversized block requires splitting.
    Changed text/settings intentionally produce new IDs; identical runs do not.
    """
    if strategy not in {'fixed', 'structure'}:
        raise ValueError('strategy must be fixed or structure')
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError('Require chunk_size > 0 and 0 <= overlap < chunk_size')
    chunks = []
    splitter = _fixed if strategy == 'fixed' else _structure
    for document in documents:
        for position, text in enumerate(splitter(document.text, chunk_size, overlap)):
            identity = json.dumps([document.metadata['document_id'], strategy,
                                   chunk_size, overlap, position, text], ensure_ascii=False)
            metadata = {**document.metadata,
                        'chunk_id': hashlib.sha256(identity.encode()).hexdigest(),
                        'chunking_strategy': strategy}
            chunks.append(Document(text, metadata))
    return chunks


CONFIGURATIONS = {
    'A': {'strategy': 'fixed', 'target': 300, 'overlap': 45},
    'B': {'strategy': 'fixed', 'target': 500, 'overlap': 75},
    'C': {'strategy': 'structure', 'target': 800, 'overlap': 0},
}
TOKEN_METHOD = 'offline-word-pieces-4chars-plus-punctuation-v1'


def structure_ranges(text: str, size: int, headings: list[str]) -> list[tuple[int, int]]:
    """Keep source subsections/procedures intact when they fit; pack small units."""
    from app.rag.preprocessing import heading_match
    boundaries = {0, len(text)}
    for title in headings:
        match = heading_match(text, title)
        if match:
            boundaries.add(match.start())
    # Paragraph boundaries are usable unless a numbered procedure spans pages.
    for match in re.finditer(r'\n\s*\n', text):
        following = text[match.end():]
        previous = text[:match.start()]
        continuation = re.match(r'(\d+)[.)]?\s+', following)
        if continuation and int(continuation[1]) > 1 and re.search(r'(?m)^1[.)]?\s+', previous):
            continue
        boundaries.add(match.end())
    # Start a unit at a numbered procedure, carrying its immediately preceding
    # source heading or warning. This separates setup prose from the actual steps.
    for match in re.finditer(r'(?m)^1[.)]?\s+', text):
        previous_end = match.start()
        previous_start = text.rfind('\n', 0, max(0, previous_end-1)) + 1
        previous_line = text[previous_start:previous_end].strip()
        if previous_line and len(previous_line.split()) < 20 and (
                not re.search(r'[.!?]$', previous_line)
                or re.match(r'(Warning|Caution|Note)[:：]', previous_line, re.I)):
            boundaries.add(previous_start)
        else:
            boundaries.add(match.start())
    points = sorted(boundaries)
    units = [(a, b) for a, b in zip(points, points[1:]) if text[a:b].strip()]
    # Attach tiny heading/paragraph units before packing; do not emit orphan headings.
    merged = []
    index = 0
    while index < len(units):
        a, b = units[index]
        while approximate_token_count(text[a:b]) < 50 and index + 1 < len(units):
            index += 1
            b = units[index][1]
        merged.append((a, b))
        index += 1
    if len(merged) > 1 and approximate_token_count(text[slice(*merged[-1])]) < 50:
        last = merged.pop()
        merged[-1] = (merged[-1][0], last[1])
    ranges = []
    pending = None
    for a, b in merged:
        if pending is not None and approximate_token_count(text[pending:b]) <= size:
            continue
        if pending is not None:
            ranges.append((pending, a))
        pending = a
        if approximate_token_count(text[a:b]) > size:
            ranges.append((a, b))  # Caller splits oversized units with repeated context.
            pending = None
    if pending is not None:
        ranges.append((pending, len(text)))
    return ranges


def chunk_sections(sections: list[Document], configuration: str) -> list[Document]:
    """Chunk the same safe runs with source headings and exact page mapping.

    All emitted body text is a source substring. Repeated heading/context comes
    only from source/bookmark text and is identified separately in metadata.
    """
    from app.rag.preprocessing import stable_id
    config = CONFIGURATIONS[configuration]
    output = []
    for section in sections:
        title = section.metadata['section_title']
        prefix = title + '\n\n'
        budget = max(1, config['target'] - approximate_token_count(prefix))
        ranges = (word_windows(section.text, budget, min(config['overlap'], budget-1))
                  if config['strategy'] == 'fixed'
                  else structure_ranges(section.text, budget, section.metadata.get('headings', [])))
        pieces = []
        for a, b in ranges:
            context = ''
            if config['strategy'] == 'structure' and approximate_token_count(section.text[a:b]) > budget:
                # Preserve the unit's actual heading/introduction for split procedures.
                context_end = word_windows(section.text[a:b], min(80, budget//3), 0)[0][1]
                context = section.text[a:a+context_end] + '\n\n'
                remaining = max(1, budget - approximate_token_count(context))
                for x, y in word_windows(section.text[a:b], remaining, 0):
                    pieces.append((a+x, a+y, context, (a, a+context_end)))
            else:
                pieces.append((a, b, '', None))
        for index, (a, b, context, context_range) in enumerate(pieces):
            body = section.text[a:b].strip()
            text = prefix + context + body
            spans = section.metadata['page_spans']
            ranges_used = [(a, b)] + ([context_range] if context_range else [])
            pages = sorted({span['page'] for span in spans
                            if any(span['start'] < end and span['end'] > start
                                   for start, end in ranges_used)})
            body_pages = pages[:]
            pages = sorted(set(pages + [section.metadata['page_start']]))
            metadata = {key: value for key, value in section.metadata.items()
                        if key not in {'page_spans', 'headings'}}
            metadata.update(configuration=configuration,
                            chunking_strategy=config['strategy'],
                            chunk_id=stable_id(section.metadata['section_id'],
                                               str(section.metadata['section_part']),
                                               configuration, str(config), str(index), text),
                            token_count=approximate_token_count(text), token_method=TOKEN_METHOD,
                            page_start=min(pages), page_end=max(pages), pages=pages, body_pages=body_pages,
                            body_start=a, body_end=b, context_repeated=bool(context),
                            heading_context=title,
                            heading_page=section.metadata['page_start'])
            output.append(Document(text, metadata))
    return output
