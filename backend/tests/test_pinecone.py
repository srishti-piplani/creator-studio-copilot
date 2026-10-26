"""Mocked Pinecone tests; no network calls or real keys."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from app.config import PineconeSettings
from app.rag.pinecone_records import load_records, namespace_for, record_id, to_record
from app.rag.pinecone_store import PineconeOperationError, PineconeStore, check_compatible, with_retry, as_dict
from app.rag.retrieve import parse_results, search

FIXTURE = json.loads((Path(__file__).parent/'fixtures/pinecone_synthetic.json').read_text())


def description():
    return {'name':'test-index','dimension':1024,'metric':'cosine','vector_type':'dense',
            'host':'https://unit-test.invalid','status':{'ready':True},
            'spec':{'serverless':{'cloud':'aws','region':'us-east-1'}},
            'embed':{'model':'llama-text-embed-v2','field_map':{'text':'chunk_text'},
                     'read_parameters':{'input_type':'query','truncate':'NONE','dimension':1024},
                     'write_parameters':{'input_type':'passage','truncate':'NONE','dimension':1024}}}


class APIError(Exception):
    def __init__(self,status):
        self.status=status
        super().__init__('secret request content that must never be logged')


class PineconeTests(unittest.TestCase):
    def settings(self):
        return PineconeSettings(api_key='unit-test-secret',index_name='test-index')

    def connected(self):
        client=Mock()
        client.list_indexes.return_value.names.return_value=['test-index']
        client.describe_index.return_value=description()
        store=PineconeStore(self.settings(),client=client,sleep=Mock())
        store.ensure_index()
        return store

    def test_installed_sdk_nested_model_serialization(self):
        from pinecone.core.openapi.inference.model.model_info_list import ModelInfoList
        from pinecone.core.openapi.inference.model.model_info import ModelInfo
        from pinecone.core.openapi.inference.model.model_info_supported_metrics import ModelInfoSupportedMetrics
        from pinecone.core.openapi.inference.model.model_info_metric import ModelInfoMetric
        info=ModelInfo(model='llama-text-embed-v2',short_description='test',type='embed',
                       supported_parameters=[],vector_type='dense',
                       supported_metrics=ModelInfoSupportedMetrics([ModelInfoMetric('cosine')]),
                       supported_dimensions=[1024],default_dimension=1024)
        result=as_dict(ModelInfoList(models=[info]))
        self.assertEqual(result['models'][0]['supported_metrics'],['cosine'])
        json.dumps(result)

    def test_installed_sdk_fetch_response_serialization(self):
        from pinecone.db_data.dataclasses.fetch_response import FetchResponse
        from pinecone.db_data.dataclasses.vector import Vector
        from pinecone.core.openapi.db_data.model.usage import Usage
        response=FetchResponse(namespace='integration-test',
                               vectors={'id':Vector(id='id',values=[0.1],metadata={'synthetic':True})},
                               usage=Usage(read_units=1))
        result=as_dict(response)
        self.assertTrue(result['vectors']['id']['metadata']['synthetic'])
        self.assertEqual(result['usage']['read_units'],1)
        json.dumps(result)

    def test_secret_excluded_from_settings_representation(self):
        self.assertNotIn('unit-test-secret',repr(self.settings()))

    def test_compatible_index_reused_without_modification(self):
        store=self.connected()
        store.client.create_index_for_model.assert_not_called()
        store.client.configure_index.assert_not_called()
        store.client.Index.assert_called_once_with(host='https://unit-test.invalid')

    def test_index_incompatibilities_fail_closed(self):
        for key,value in [('dimension',512),('metric','dotproduct'),('vector_type','sparse')]:
            desc=description();desc[key]=value
            with self.assertRaises(ValueError):check_compatible(desc,self.settings())
        for key,value in [('model','another-model'),('field_map',{'text':'other'}),('write_parameters',{'truncate':'END'})]:
            desc=description();desc['embed'][key]=value
            with self.assertRaises(ValueError):check_compatible(desc,self.settings())
        store=PineconeStore(self.settings(),client=Mock())
        store.client.list_indexes.return_value.names.return_value=['test-index','unrelated']
        desc=description();desc['embed']={}
        store.client.describe_index.return_value=desc
        with self.assertRaises(ValueError):store.ensure_index()
        store.client.create_index_for_model.assert_not_called()
        store.client.configure_index.assert_not_called()
        store.client.delete_index.assert_not_called()

    def test_missing_index_creation_checks_existing_indexes_first(self):
        client=Mock()
        client.list_indexes.return_value.names.return_value=['unrelated']
        client.describe_index.return_value=description()
        store=PineconeStore(self.settings(),client=client,sleep=Mock())
        store.ensure_index()
        options=client.create_index_for_model.call_args.kwargs
        self.assertEqual(options['name'],'test-index')
        self.assertEqual(options['embed']['field_map'],{'text':'chunk_text'})
        self.assertEqual(options['embed']['write_parameters']['truncate'],'NONE')
        client.delete_index.assert_not_called()

    def test_query_connection_does_not_create_missing_index(self):
        client=Mock();client.list_indexes.return_value.names.return_value=[]
        with self.assertRaises(ValueError):PineconeStore(self.settings(),client=client).ensure_index(create=False)
        client.create_index_for_model.assert_not_called()

    def test_metadata_projection_and_unknown_versions(self):
        row=deepcopy(FIXTURE[0]);row['metadata']['software_version']='test-only'
        record=to_record(row,'A',synthetic_only=True)
        self.assertEqual(record['pages'],['1'])
        self.assertEqual(record['software_version'],'test-only')
        self.assertEqual(record['source_url'],row['metadata']['source_url'])
        self.assertEqual(record['chunk_id'],row['metadata']['chunk_id'])
        row['metadata']['version']=None;row['metadata'].pop('software_version')
        row['metadata']['source_url']=None
        record=to_record(row,'A')
        self.assertNotIn('version',record)
        self.assertNotIn('source_url',record)
        self.assertFalse(record['version_known'])

    def test_metadata_validation(self):
        cases=[('product','GarageBand'),('page_start',0),('page_end',False),
               ('configuration','B'),('chunking_strategy','structure'),
               ('document_title',None),('version',{'nested':'not allowed'}),
               ('source_url','javascript:invalid'),('pages',[999])]
        for name,value in cases:
            row=deepcopy(FIXTURE[0]);row['metadata'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):to_record(row,'A')
        row=deepcopy(FIXTURE[0]);row['text']='x'*50000
        with self.assertRaises(ValueError):to_record(row,'A')
        row=deepcopy(FIXTURE[0]);row['text']+='\ufffd'
        with self.assertRaises(ValueError):to_record(row,'A')

    def test_namespace_routing_and_stable_ids(self):
        self.assertEqual([namespace_for(c) for c in 'ABC'],['small-300','medium-500','structure-aware'])
        row=deepcopy(FIXTURE[0])
        self.assertEqual(record_id(row['metadata']),to_record(row,'A')['_id'])
        self.assertEqual(to_record(row,'A'),to_record(deepcopy(row),'A'))
        old=record_id(row['metadata']);row['metadata']['chunk_id']='changed'
        self.assertNotEqual(old,record_id(row['metadata']))
        with self.assertRaises(ValueError):namespace_for('D')
        store=self.connected()
        with self.assertRaises(ValueError):store.upsert([to_record(FIXTURE[0],'A')],'medium-500')

    def test_retry_transient_and_permanent_errors_are_sanitized(self):
        sleep=Mock();operation=Mock(side_effect=[APIError(429),APIError(503),'ok'])
        self.assertEqual(with_retry(operation,sleep=sleep),'ok')
        self.assertEqual(operation.call_count,3)
        self.assertEqual(sleep.call_count,2)
        for status,attempts in [(400,1),(401,1),(403,1),(503,3)]:
            operation=Mock(side_effect=APIError(status))
            with self.assertRaises(PineconeOperationError) as caught:
                with_retry(operation,sleep=Mock())
            self.assertEqual(operation.call_count,attempts)
            self.assertNotIn('secret',str(caught.exception))
        self.assertEqual(with_retry(Mock(side_effect=[TimeoutError(),'ok']),sleep=Mock()),'ok')

    def test_batched_upsert_and_retry_uses_identical_ids(self):
        store=self.connected();records=[to_record(row,'A') for row in FIXTURE]
        store.index.upsert_records.side_effect=[APIError(503),None,None,None]
        self.assertEqual(store.upsert(records,'integration-test',batch_size=2),5)
        calls=store.index.upsert_records.call_args_list
        self.assertEqual([c.kwargs['records'][0]['_id'] for c in calls[:2]], [records[0]['_id']]*2)
        self.assertTrue(all(c.kwargs['namespace']=='integration-test' for c in calls))
        self.assertEqual([len(c.kwargs['records']) for c in calls],[2,2,2,1])

    def test_live_namespace_rejects_real_content(self):
        store=self.connected();row=deepcopy(FIXTURE[0]);row['metadata']['synthetic']=False
        with self.assertRaises(ValueError):to_record(row,'A',synthetic_only=True)
        with self.assertRaises(ValueError):store.upsert([to_record(row,'A')],'integration-test')
        store.index.upsert_records.assert_not_called()
        with self.assertRaises(ValueError):store.upsert([], 'integration-test',batch_size=97)

    def test_load_jsonl_and_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chunks.jsonl'
            path.write_text(json.dumps(FIXTURE[0])+'\n')
            self.assertEqual(len(load_records(path,'A')),1)
            path.write_text((json.dumps(FIXTURE[0])+'\n')*2)
            with self.assertRaises(ValueError):load_records(path,'A')

    def test_retrieval_requires_citation_metadata_and_normalizes_numeric_pages(self):
        record=to_record(FIXTURE[0],'A')
        fields={k:v for k,v in record.items() if k!='_id'}
        fields['page_start']=1.0;fields['page_end']=1.0
        response={'result':{'hits':[{'_id':record['_id'],'_score':0.8,'fields':fields}]}}
        self.assertIs(type(parse_results(response)[0]['metadata']['page_start']),int)
        del fields['document_title']
        with self.assertRaises(PineconeOperationError):parse_results(response)

    def test_retrieval_parsing_and_product_filter(self):
        store=self.connected();record=to_record(FIXTURE[0],'A')
        fields={k:v for k,v in record.items() if k!='_id'}
        store.index.search.return_value={'result':{'hits':[{'_id':record['_id'],'_score':0.8,'fields':fields}]}}
        hits=search(store,'synthetic question','small-300',product='Logic Pro')
        self.assertEqual(hits[0]['text'],FIXTURE[0]['text'])
        self.assertEqual(hits[0]['metadata']['pages'],[1])
        self.assertEqual(hits[0]['metadata']['source_url'],FIXTURE[0]['metadata']['source_url'])
        query=store.index.search.call_args.kwargs['query']
        self.assertEqual(query['filter'],{'product':{'$eq':'Logic Pro'}})
        self.assertEqual(query['inputs'],{'text':'synthetic question'})
        with self.assertRaises(ValueError):search(store,'question','small-300',product='iMovie')
        self.assertEqual(parse_results({'result':{'hits':[]}}),[])
        with self.assertRaises(PineconeOperationError):parse_results({'result':{'hits':[{'_id':'x','_score':0.3,'fields':{}}]}})


if __name__=='__main__':
    unittest.main()
