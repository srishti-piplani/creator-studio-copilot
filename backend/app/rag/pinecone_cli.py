"""Explicit synthetic-only Pinecone smoke test; never reads manual datasets."""

import argparse
import json
import time
from pathlib import Path

from app.config import PineconeSettings
from app.rag.pinecone_records import to_record
from app.rag.pinecone_store import PineconeStore, as_dict, PineconeOperationError
from app.rag.retrieve import search

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'backend/tests/fixtures/pinecone_synthetic.json'
REPORT = ROOT / 'evaluations/pinecone_integration.json'


def integration_test(store):
    # Fixed test-only input path: the live smoke test never reads the real corpus.
    chunks = json.loads(FIXTURE.read_text())
    if len(chunks) != 5:
        raise ValueError('Integration fixture must contain exactly five synthetic chunks')
    records = [to_record(chunk, 'A', synthetic_only=True) for chunk in chunks]
    report = {'status': 'running', 'namespace': 'integration-test', 'synthetic_only': True,
              'index_name': store.settings.index_name, 'stage': 'model-discovery'}
    try:
        catalog = as_dict(store.call(lambda: store.client.inference.list_models(type='embed')))
        report['available_embedding_models'] = [m['model'] for m in catalog['models']]
        selected = next((m for m in catalog['models'] if m['model']==store.settings.model), None)
        if selected is None or selected.get('vector_type') != 'dense' or store.settings.dimension not in selected.get('supported_dimensions', []):
            raise ValueError('Configured integrated embedding model is unavailable/incompatible')
        report['model_capabilities'] = selected
        report['stage'] = 'index-configuration'
        began = time.perf_counter()
        description = store.ensure_index()
        report['index_configuration_seconds'] = round(time.perf_counter()-began, 4)
        report['index_configuration'] = {key: description[key] for key in
                                         ('name','dimension','metric','vector_type','embed','spec')}
        report['stage'] = 'synthetic-upsert'
        began = time.perf_counter()
        count = store.upsert(records, 'integration-test', batch_size=5)
        report['records_upserted'] = count
        report['upsert_seconds'] = round(time.perf_counter()-began, 4)
        indexed_at = began
        report['stage'] = 'eventual-consistency-check'
        expected = {record['_id']: record for record in records}
        for attempt in range(30):
            fetched = as_dict(store.call(lambda: store.index.fetch(ids=list(expected), namespace='integration-test')))
            actual = fetched.get('vectors', {})
            if set(expected) <= set(actual):
                for identity, record in expected.items():
                    fields = as_dict(actual[identity]).get('metadata', {})
                    if any(fields.get(key) != value for key,value in record.items() if key!='_id'):
                        raise ValueError('Stored synthetic text/metadata differs from fixture')
                break
            if attempt == 29:
                raise PineconeOperationError('Synthetic records did not become visible within polling budget')
            store.sleep(2)
        report['indexing_until_visible_seconds'] = round(time.perf_counter()-indexed_at, 4)
        report['stored_text_and_metadata_verified'] = True
        report['stage'] = 'semantic-queries'
        queries = [
            ('How can I hear my microphone immediately without computer audio delay?', records[1], None),
            ('How do I save my finished movie as a video file?', records[3], 'DaVinci Resolve')]
        report['queries'] = []
        for number,(query, expected_record, product) in enumerate(queries,1):
            began = time.perf_counter()
            results = search(store, query, 'integration-test', top_k=3,
                             product=product, synthetic_only=True)
            elapsed = round(time.perf_counter()-began, 4)
            passed = bool(results) and results[0]['record_id']==expected_record['_id']
            for hit in results:
                if hit['record_id'] not in expected or hit['text'] != expected[hit['record_id']]['chunk_text']:
                    raise ValueError('Retrieved passage differs from synthetic fixture')
                fields = hit['metadata']
                if fields.get('synthetic') is not True or product and fields.get('product') != product:
                    raise ValueError('Synthetic/product filter was not respected')
            report['queries'].append({'number': number,'seconds': elapsed,'top_match_correct': passed,
                                      'product_filter': product,'returned_records':len(results),
                                      'top_score':results[0]['score'] if results else None,
                                      'returned_ids':[hit['record_id'] for hit in results]})
            if not passed:
                raise ValueError('Semantic query did not rank expected fixture first')
        report.update(status='passed',stage='complete',namespace_retained=True,
                      real_document_records_uploaded=0)
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__,
                      error=(str(error) if isinstance(error, (PineconeOperationError, ValueError))
                             else 'Failure details suppressed to protect credentials and request content.'),
                      namespace_retained=True)
        raise
    finally:
        REPORT.write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Explicit synthetic-only Pinecone smoke test (writes five labeled test records).')
    parser.add_argument('command', choices=['integration-test'])
    parser.parse_args()
    try:
        report = integration_test(PineconeStore(PineconeSettings.from_env()))
        print(json.dumps({key: report[key] for key in (
            'status', 'index_name', 'namespace', 'records_upserted',
            'upsert_seconds', 'indexing_until_visible_seconds', 'queries')}, indent=2))
    except Exception as error:
        print(f'Synthetic integration test failed ({type(error).__name__}); sensitive details suppressed.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
