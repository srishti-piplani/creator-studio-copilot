"""Load and clean local documents. This module never fetches source URLs."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from pypdf import PdfReader

from app.config import EXCLUDED_CORPUS_DIRECTORIES, SUPPORTED_PRODUCTS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED = {'.pdf', '.md', '.txt'}


@dataclass
class Document:
    text: str
    metadata: dict


def clean_text(text: str) -> str:
    """Normalize horizontal space while preserving paragraph and heading boundaries."""
    lines = [re.sub(r'[^\S\n]+', ' ', line).strip() for line in text.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def clean_pdf_pages(pages: list[str]) -> str:
    """Remove matching first/last lines on most pages, plus standalone page numbers.

    Only edge lines repeated on at least three pages qualify; interior text stays.
    """
    lines = [clean_text(page).splitlines() for page in pages]
    edges = Counter()
    for page in lines:
        if page:
            edges.update(set((page[0], page[-1])))
    repeated = {line for line, count in edges.items()
                if count >= max(3, (len(pages) + 1) // 2)}
    cleaned = []
    for page in lines:
        kept = [line for i, line in enumerate(page)
                if not (i in (0, len(page) - 1)
                        and (line in repeated or re.fullmatch(r'(?:Page\s+)?\d+', line, re.I)))]
        cleaned.append('\n'.join(kept))
    return clean_text('\n\n'.join(cleaned))


def load_documents(corpus_dir: str | Path | None = None,
                   manifest_path: str | Path | None = None,
                   *, allowed_products: tuple[str, ...] = SUPPORTED_PRODUCTS) -> list[Document]:
    """Load supported files recursively. Manifest paths are relative to corpus_dir.

    Only manifest-listed products in the explicit allowlist are loaded.
    Tests may supply their own explicit allowlist for synthetic products.
    IDs use relative paths, so moving the corpus directory does not change IDs.
    """
    corpus = Path(corpus_dir or os.environ.get('CORPUS_DIR', PROJECT_ROOT / 'data/corpus')).resolve()
    manifest = Path(manifest_path or PROJECT_ROOT / 'data/sources.json')
    if not corpus.is_dir():
        raise ValueError(f'Corpus directory does not exist: {corpus}')
    entries = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(entries, list):
        raise ValueError('Source manifest must be a JSON array')
    by_path = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            raise ValueError('Every manifest entry needs a string path')
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Manifest paths must stay inside the corpus directory')
        key = relative.as_posix()
        if key in by_path:
            raise ValueError(f'Duplicate manifest path: {key}')
        by_path[key] = entry
    documents = []
    for path in sorted(corpus.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        if not path.resolve().is_relative_to(corpus):
            raise ValueError(f'File escapes corpus directory: {path}')
        relative = path.relative_to(corpus).as_posix()
        entry = by_path.get(relative, {})
        if (entry.get('product') not in allowed_products
                or Path(relative).parts[0] in EXCLUDED_CORPUS_DIRECTORIES):
            continue
        if path.suffix.lower() == '.pdf':
            text = clean_pdf_pages([page.extract_text() or '' for page in PdfReader(path).pages])
        else:
            text = clean_text(path.read_text(encoding='utf-8-sig'))
        if not text:
            continue  # Scanned PDFs require OCR, which is not implemented.
        metadata = {key: entry[key] for key in (
            'software_version', 'hardware_generation') if entry.get(key) is not None}
        metadata.update(document_id=hashlib.sha256(relative.encode()).hexdigest(),
                        product=entry.get('product', 'unknown'),
                        topic=entry.get('topic', 'unknown'),
                        source_url=entry.get('source_url'),
                        document_title=entry.get('document_title', path.stem))
        documents.append(Document(text, metadata))
    return documents


def product_coverage(documents: list[Document]) -> dict[str, str]:
    """Availability reflects nonempty documents actually loaded, not manifest claims."""
    present = {document.metadata['product'] for document in documents}
    return {product: 'available' if product in present else 'unavailable'
            for product in SUPPORTED_PRODUCTS}


def main() -> None:
    from app.rag.chunking import chunk_documents, approximate_token_count

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-dir', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    documents = load_documents(args.corpus_dir, args.manifest)
    print(f'Documents loaded: {len(documents)}')
    print('MVP coverage:', json.dumps(product_coverage(documents)))
    for strategy in ('fixed', 'structure'):
        chunks = chunk_documents(documents, strategy=strategy)
        counts = [approximate_token_count(chunk.text) for chunk in chunks]
        print(f'{strategy}: {len(chunks)} chunks; approximate token counts: {counts}')
        if chunks:
            print('Example metadata:', json.dumps(chunks[0].metadata, sort_keys=True))


if __name__ == '__main__':
    main()
