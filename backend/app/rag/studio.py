"""Prepare and validate authored Studio guides without manufacturer-manual inputs."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from app.config import SUPPORTED_PRODUCTS
from app.rag.ingest import Document, PROJECT_ROOT, load_documents
from app.rag.chunking import chunk_sections
from app.rag.prepare import verify_source_coverage, write_jsonl
from app.rag.pinecone_records import to_record

GUIDES = PROJECT_ROOT / 'data/studio_knowledge'
OUTPUT = PROJECT_ROOT / 'data/studio_processed'


def validate_guides(directory=GUIDES):
    manifest=json.loads((directory/'manifest.json').read_text())
    references={r['id']:r for r in manifest['references']}
    if len(references)!=len(manifest['references']):
        raise ValueError('Duplicate reference IDs')
    ids=set(); paths=set()
    for guide in manifest['guides']:
        if guide['source_id'] in ids or guide['path'] in paths:
            raise ValueError('Duplicate Studio guide identity/path')
        ids.add(guide['source_id']);paths.add(guide['path'])
        path=(directory/guide['path']).resolve()
        if not path.is_relative_to(directory.resolve()) or path.suffix!='.md':
            raise ValueError('Studio guide path must stay in its own corpus')
        text=path.read_text()
        if hashlib.sha256(text.encode()).hexdigest()!=guide['sha256']:
            raise ValueError('Guide changed after reference review')
        if len(text.split())<300 or len(re.findall(r'(?m)^## ',text))<3:
            raise ValueError('Guide lacks substantial structured explanations')
        if guide['review_status']!='reference-supported' or not guide['reference_ids']:
            raise ValueError('Missing technical reference review')
        for identity in guide['reference_ids']:
            reference=references[identity]
            if not reference.get('checked_on') or not reference.get('verification_scope') or not reference['url'].startswith('https://'):
                raise ValueError('Unverified reference')
        if '\ufffd' in text:
            raise ValueError('Corrupt guide text')
    return manifest


def prepare_studio():
    manifest=validate_guides(GUIDES)
    references={r['id']:r for r in manifest['references']}
    sources=[{'path':g['path'],'product':'Studio fundamentals','topic':g['title'],
              'document_title':g['title'],'source_url':'studio://'+g['source_id']} for g in manifest['guides']]
    (GUIDES/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
    loaded=load_documents(GUIDES,GUIDES/'sources.json',allowed_products=('Studio fundamentals',))
    by_title={g['title']:g for g in manifest['guides']}
    sections=[]
    for doc in loaded:
        guide=by_title[doc.metadata['document_title']]
        metadata={**doc.metadata,'document_id':guide['source_id'],'source_id':guide['source_id'],
                  'section_id':hashlib.sha256((guide['source_id']+guide['sha256']).encode()).hexdigest(),
                  'section_title':guide['title'],'section_part':0,'page_start':1,'page_end':1,
                  'page_spans':[{'start':0,'end':len(doc.text),'page':1}],
                  'headings':re.findall(r'(?m)^## (.+)$',doc.text),
                  'corpus':'studio-original','version':'studio-1',
                  'guide_path':'data/studio_knowledge/'+guide['path'],
                  'authorship':guide['authorship'],'page_reference_type':'markdown-logical-page',
                  'source_sha256':guide['sha256'],
                  'applies_to':list(SUPPORTED_PRODUCTS),
                  'reference_urls':[references[r]['url'] for r in guide['reference_ids']]}
        sections.append(Document(doc.text,metadata))
    OUTPUT.mkdir(exist_ok=True)
    write_jsonl(OUTPUT/'sections.jsonl',[{'text':s.text,'metadata':s.metadata} for s in sections])
    counts={}
    for strategy in 'ABC':
        chunks=chunk_sections(sections,strategy)
        verify_source_coverage(sections,chunks)
        lookup={s.metadata['section_id']:s.text for s in sections}
        for chunk in chunks:
            source=lookup[chunk.metadata['section_id']]
            chunk.metadata['source_line_start']=source.count('\n',0,chunk.metadata['body_start'])+1
            chunk.metadata['source_line_end']=source.count('\n',0,chunk.metadata['body_end'])+1
            to_record({'text':chunk.text,'metadata':chunk.metadata},strategy)
        (OUTPUT/strategy).mkdir(exist_ok=True)
        write_jsonl(OUTPUT/strategy/'chunks.jsonl',[{'text':c.text,'metadata':c.metadata} for c in chunks])
        counts[strategy]=len(chunks)
    review={'guides':len(sections),'words':sum(len(s.text.split()) for s in sections),
            'chunk_counts':counts,
            'originality_limit':'Original AI-assisted guides with recorded references; no manual comparison or comprehensive plagiarism audit is performed during preparation.',
            'technical_review':'Reference claims/excerpts checked by the authoring assistant, not independently human-reviewed.',
            'manual_records_uploaded':0,'same_retained_text':True}
    (PROJECT_ROOT/'evaluations/studio_preparation.json').write_text(json.dumps(review,indent=2)+'\n')
    return review


if __name__=='__main__':
    print(json.dumps(prepare_studio(),indent=2))
