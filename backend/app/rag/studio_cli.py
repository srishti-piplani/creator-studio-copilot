"""Studio-only preparation, indexing, retrieval evaluation and grounded examples."""

import argparse
import json
import statistics
import time

from app.config import PineconeSettings
from app.rag.pinecone_records import STUDIO_NAMESPACES, load_records
from app.rag.pinecone_store import PineconeStore, as_dict
from app.rag.retrieve import search
from app.rag.studio import OUTPUT, PROJECT_ROOT, prepare_studio
from app.rag.generate import get_rag_service


def connected():
    store=PineconeStore(PineconeSettings.from_env())
    store.ensure_index(create=False)
    return store


def index_studio():
    # Only this original-guide builder supplies upload input. No manual path option.
    review=prepare_studio()
    datasets={c:load_records(OUTPUT/c/'chunks.jsonl',c) for c in 'ABC'}
    if any(r.get('corpus')!='studio-original' for rows in datasets.values() for r in rows):
        raise ValueError('Only original Studio records may be uploaded')
    store=connected();timings={}
    for c,records in datasets.items():
        start=time.perf_counter()
        count=store.upsert(records,STUDIO_NAMESPACES[c])
        upsert_seconds=time.perf_counter()-start
        # Verify every ID and original text before evaluating retrieval.
        expected={r['_id']:r for r in records}
        for attempt in range(30):
            fetched=as_dict(store.call(lambda:store.index.fetch(ids=list(expected),namespace=STUDIO_NAMESPACES[c])))
            vectors=fetched.get('vectors',{})
            if set(expected)<=set(vectors) and all(vectors[i]['metadata']['chunk_text']==r['chunk_text'] for i,r in expected.items()):
                break
            if attempt==29:raise ValueError('Studio records not fully visible within bounded polling')
            store.sleep(2)
        timings[c]={'namespace':STUDIO_NAMESPACES[c],'records_verified':count,
                    'upsert_seconds':round(upsert_seconds,4),
                    'through_visibility_seconds':round(time.perf_counter()-start,4)}
        print(f'{STUDIO_NAMESPACES[c]}: {count} original records verified',flush=True)
    report={'status':'passed','model':'llama-text-embed-v2','index_name':store.settings.index_name,
            'manual_records_uploaded':0,'namespaces':timings,'preparation':review}
    (PROJECT_ROOT/'evaluations/studio_indexing.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def retrieval_evaluation():
    # Labels are evaluation-only; request handlers never load this dataset.
    from scripts.golden_sets import load_golden
    golden=load_golden('golden_questions.json', 'rag_only')
    store=connected();report={}
    for configuration,namespace in STUDIO_NAMESPACES.items():
        rows=[]
        for question in golden:
            start=time.perf_counter()
            hits=search(store,question['question'],namespace,top_k=5)
            seconds=time.perf_counter()-start
            actual={h['metadata']['source_id'] for h in hits}
            expected=set(question['relevant_source_ids'])
            rows.append({'id':question['id'],'rag_answerable':question['rag_answerable'],
                         'recall_at_5':len(actual&expected)/len(expected) if expected else None,
                         'expected_source_ids':sorted(expected),'retrieved_source_ids':sorted(actual),
                         'seconds':round(seconds,4)})
        recalls=[r['recall_at_5'] for r in rows if r['rag_answerable']]
        times=sorted(r['seconds'] for r in rows)
        report[configuration]={'namespace':namespace,'questions':len(rows),'rag_answerable_questions':len(recalls),
                               'source_recall_at_5':statistics.mean(recalls),
                               'mean_seconds':statistics.mean(times),'median_seconds':statistics.median(times),
                               'p95_seconds':times[max(0,(95*len(times)+99)//100-1)],'results':rows}
        print(configuration,'Recall@5',round(report[configuration]['source_recall_at_5'],4),flush=True)
    result={'metric_definition':'Macro average of relevant GUIDE IDs retrieved in top five CHUNKS, across RAG-answerable questions. RAG-unsupported questions excluded from recall denominator; retrieval is not answerability detection.',
            'evaluation_scope':'rag_only','golden_set':'data/golden_questions.json','golden_answers_independent_of_live_generation':True,
            'strategies':report,'limitations':['Small author-designed set, not an unbiased benchmark.','No winning strategy declared; answer factuality requires a separate review.', 'Negative retrieval does not measure refusal accuracy or full-agent answerability.', 'studio-q17 wording revised in Phase 5A; positive queries and the recall denominator are unchanged.']}
    (PROJECT_ROOT/'evaluations/studio_retrieval.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def run_examples():
    questions=['What is the difference between direct and software monitoring?',
               'How does EQ differ from compression?',
               'Why might audio and video drift out of sync?',
               'What is the exact phantom-power current consumption of an AT2035?']
    rag=get_rag_service();rows=[]
    for question in questions:
        answer=rag.answer(question,'B')
        rows.append({'question':question,**answer})
        print('Grounded example completed; answerable:',answer['answerable'],flush=True)
    result={'provider':'Nebius','model':rag.chat.settings.model,'strategy':'B',
            'examples':rows,'limitations':'Citation IDs and known guide revisions are validated. This is not independent claim-level fact checking.'}
    (PROJECT_ROOT/'evaluations/studio_rag_examples.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','index','evaluate','examples','ask'])
    parser.add_argument('--question');parser.add_argument('--strategy',choices=list('ABC'),default='B')
    args=parser.parse_args()
    try:
        if args.command=='prepare':print(json.dumps(prepare_studio(),indent=2))
        elif args.command=='index':index_studio()
        elif args.command=='evaluate':retrieval_evaluation()
        elif args.command=='examples':run_examples()
        elif args.question:print(json.dumps(get_rag_service().answer(args.question,args.strategy),indent=2))
        else:parser.error('--question is required')
    except Exception as error:
        print(f'Studio command failed ({type(error).__name__}); sensitive service details suppressed.')
        raise SystemExit(1) from None


if __name__=='__main__':main()
