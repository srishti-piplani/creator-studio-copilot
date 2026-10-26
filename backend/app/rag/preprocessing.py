"""Conservative, page-aware local PDF preparation. Never reconstruct missing text."""

from collections import Counter
import hashlib
import re

from app.rag.ingest import Document, clean_text

PIPELINE_VERSION = '2b-v1'


def stable_id(*values: str) -> str:
    return hashlib.sha256('\0'.join(values).encode()).hexdigest()


def heading_match(text: str, title: str):
    """Bookmark titles may wrap and contain NBSPs; match whole heading words."""
    words = title.split()
    pattern = r'(?m)^' + r'\s+'.join(re.escape(w) for w in words) + r'(?=\s|$)'
    return re.search(pattern, text, re.I)


def repeated_edges(pages: dict[int, str]) -> set[str]:
    """Inspect three lines per edge, including headers beside separate page labels.

    Require exact repetition on >=3 distinct pages; never infer missing symbols.
    Only multiword lines qualify, avoiding single-word instructional headings.
    """
    counts = Counter()
    for text in pages.values():
        lines = clean_text(text).splitlines()
        counts.update(set(line for line in lines[:3] + lines[-3:]
                          if len(line.split()) >= 3 and len(line) < 150))
    return {line for line, count in counts.items() if count >= max(3, len(pages)//2)}


def clean_section(pages: dict[int, str], metadata: dict, edges: set[str],
                  exclusions: list[dict], seen: dict | None = None) -> list[Document]:
    """Return contiguous safe runs; rejected passages are explicit gaps.

    A paragraph containing U+FFFD or C1 controls is quarantined in full. With
    plain PDF extraction a page may be a single paragraph; conservative loss is
    preferable to joining incomplete technical instructions across corruption.
    """
    seen = {} if seen is None else seen
    review_policy = ({item['content_sha256']: item for item in metadata['passage_review']}
                     if 'passage_review' in metadata else None)
    runs = []
    current = []
    part = 0

    def reject(page, text, reason, **extra):
        exclusions.append({'document_id': metadata['document_id'],
                           'source_id': metadata['source_id'],
                           'section_id': metadata['section_id'], 'pages': [page],
                           'reason': reason, 'characters': len(text),
                           'content_sha256': stable_id(text), **extra})

    def flush():
        nonlocal current, part
        if not current:
            return
        text = ''
        spans = []
        for page, passage in current:
            if text:
                text += '\n\n'
            start = len(text)
            text += passage
            span = {'start': start, 'end': len(text), 'page': page}
            if review_policy is not None:
                review = review_policy[stable_id(passage)]
                span.update(heading=review['heading'], content_sha256=stable_id(passage),
                            review_status='approved')
            spans.append(span)
        if len(text.split()) <= 10 and not re.search(r'[.!?]|(?m:^\d+[.)]?\s+)', text):
            for page, passage in current:
                reject(page, passage, 'isolated_heading_or_caption')
            current = []
            return
        output_metadata = {key: value for key, value in metadata.items() if key != 'passage_review'}
        runs.append(Document(text, {**output_metadata, 'section_part': part,
                                   'page_start': min(p['page'] for p in spans),
                                   'page_end': max(p['page'] for p in spans),
                                   'page_spans': spans, 'pipeline_version': PIPELINE_VERSION}))
        part += 1
        current = []

    for page, raw in sorted(pages.items()):
        lines = clean_text(raw).splitlines()
        kept = []
        for index, line in enumerate(lines):
            at_edge = index < 3 or index >= len(lines)-3
            if at_edge and (line in edges or re.fullmatch(r'(?:Page\s+)?\d+', line, re.I)):
                reject(page, line, 'repeated_header_footer' if line in edges else 'page_label')
            elif at_edge and re.fullmatch(r'Chapter\s+\d+', line, re.I):
                reject(page, line, 'chapter_label')
            elif at_edge and re.match(r'^\d+\s*\w.*(?:\||Chapter)', line):
                reject(page, line, 'page_chapter_footer')
            else:
                kept.append(line)
        text = '\n'.join(kept).strip()
        # Known sheet limitations are quarantined, not converted into invented tables.
        product = metadata['product']
        cutoff = None
        if product == 'Audio-Technica AT2020':
            cutoff = heading_match(text, 'AT2020 SPECIFICATIONS')
            if cutoff is None:
                cutoff = re.search(r'(?m)^AT2020 SPECIFICATIONS', text)
        elif product == 'Audio-Technica AT2035':
            if page == 2:
                flush()
                reject(page, text, 'unreliable_specification_table_and_plot_layout')
                continue
            start = heading_match(text, 'Description')
            if start:
                reject(page, text[:start.start()], 'fragmented_feature_list')
                text = text[start.start():]
            cutoff = heading_match(text, 'Architect’s and Engineer’s Specifications')
            if cutoff is None:
                cutoff = heading_match(text, "Architect's and Engineer's Specifications")
        if cutoff:
            reject(page, text[cutoff.start():], 'unreliable_specification_table_or_nonoperational_material')
            text = text[:cutoff.start()]
        boundaries = {0, len(text)}
        boundaries.update(match.end() for match in re.finditer(r'\n\s*\n', text))
        for title in metadata.get('headings', []):
            match = heading_match(text, title)
            if match:
                boundaries.add(match.start())
        points = sorted(boundaries)
        for a, b in zip(points, points[1:]):
            passage = text[a:b]
            if not passage.strip():
                continue
            reason = None
            if '\ufffd' in passage or any(0x7f <= ord(c) <= 0x9f for c in passage):
                reason = 'corrupt_technical_passage_requires_source_review'
            # AT2035 source/extraction contains both a model mismatch and broken words.
            if product == 'Audio-Technica AT2035':
                # Isolate at printed subheadings/sentence boundaries without repairing words.
                pieces = re.split(r'(?m)(?=^Operation and Maintenance$)|(?<=\.)\n', passage)
            else:
                pieces = [passage]
            if reason:
                flush()
                reject(page, passage, reason, replacement_characters=passage.count('\ufffd'),
                       technical_risk=True)
                continue
            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue
                if product == 'Audio-Technica AT2035' and ('AT2020' in piece or re.search(r'(?m)^T\nhe\b', piece)):
                    flush()
                    reject(page, piece, 'model_mismatch_or_fragmented_word_requires_review', technical_risk=True)
                    continue
                if review_policy is not None:
                    review = review_policy.get(stable_id(piece))
                    if review is None or review['decision'] != 'include' or review['page'] != page:
                        flush()
                        reject(page, piece, 'passage_review_quarantine', technical_risk=True,
                               heading=review['heading'] if review else None,
                               review_reason=review['reason'] if review else 'No matching reviewed passage fingerprint and page; fail closed.')
                        continue
                # Deduplicate only substantial complete passages within the same source.
                signature = re.sub(r'\s+', ' ', piece).strip()
                if len(signature) >= 100 and signature in seen:
                    flush()
                    reject(page, piece, 'exact_duplicate_passage', duplicate_of=seen[signature])
                    continue
                if len(signature) >= 100:
                    seen[signature] = {'page': page, 'section_id': metadata['section_id']}
                current.append((page, piece))
    flush()
    return runs
