"""Studio isolation and grounded generation tests; all providers mocked."""

from copy import deepcopy
import json
from unittest import TestCase
from unittest.mock import Mock,patch

import httpx
from fastapi.testclient import TestClient

from app.config import ChatSettings,PineconeSettings
from app.rag.generate import ChatError,NebiusChat,StudioRAG
from app.rag.pinecone_records import STUDIO_NAMESPACES,to_record
from app.rag.pinecone_store import PineconeStore
from app.rag.studio import GUIDES,validate_guides


class StudioTests(TestCase):
    def setUp(self):
        self.manifest=validate_guides()
        self.guide=self.manifest['guides'][0]
        self.store=Mock();self.chat=Mock()
        self.hit={'record_id':'test','score':0.8,'text':'Original test evidence.',
                  'metadata':{'source_id':self.guide['source_id'],'corpus':'studio-original',
                              'source_sha256':self.guide['sha256']}}

    def test_original_guides_and_reference_manifest(self):
        self.assertEqual(len(self.manifest['guides']),12)
        self.assertTrue(all(g['independently_human_verified'] is False for g in self.manifest['guides']))
        for guide in self.manifest['guides']:
            self.assertGreaterEqual(len((GUIDES/guide['path']).read_text().split()),300)

    def test_studio_metadata_and_manual_namespace_rejection(self):
        for strategy in 'ABC':
            meta={'document_id':self.guide['source_id'],'source_id':self.guide['source_id'],
                  'product':'Studio fundamentals','document_title':self.guide['title'],
                  'section_id':'test-studio-section','section_title':'Test original section',
                  'chunk_id':'test-studio-chunk','configuration':strategy,
                  'chunking_strategy':'structure' if strategy=='C' else 'fixed',
                  'source_url':'studio://'+self.guide['source_id'],
                  'corpus':'studio-original','page_start':1,'page_end':1,
                  'reference_urls':['https://example.invalid/test-reference']}
            records=[to_record({'text':'Original synthetic test-only guide content.','metadata':meta},strategy)]
            self.assertTrue(all(r['corpus']=='studio-original' and r['reference_urls'] for r in records))
            store=PineconeStore(PineconeSettings(api_key='test'),client=Mock())
            store.index=Mock()
            self.assertEqual(store.upsert(records,STUDIO_NAMESPACES[strategy]),len(records))
            manual=deepcopy(records[0]);manual.pop('corpus')
            with self.assertRaises(ValueError):store.upsert([manual],STUDIO_NAMESPACES[strategy])
            with self.assertRaises(ValueError):store.upsert(records,'integration-test')

    def test_supported_grounded_answer_and_trusted_citation_urls(self):
        rag=StudioRAG(self.store,self.chat,manifest=self.manifest)
        self.chat.complete.return_value={'answer':'A supported explanation [S1].','answerable':True,'citation_ids':['S1']}
        with patch('app.rag.generate.search',return_value=[self.hit]) as lookup:
            result=rag.answer('What is phantom power?')
        self.assertTrue(result['answerable'])
        self.assertEqual(result['citations'][0]['source_id'],self.guide['source_id'])
        self.assertTrue(result['citations'][0]['reference_urls'])
        self.assertEqual(lookup.call_args.args[2],'studio-medium-500')
        self.assertIn('ONLY',self.chat.complete.call_args.args[0][0]['content'])

    def test_no_evidence_does_not_call_model(self):
        rag=StudioRAG(self.store,self.chat,manifest=self.manifest)
        with patch('app.rag.generate.search',return_value=[]):
            self.assertFalse(rag.answer('Unknown question')['answerable'])
        self.chat.complete.assert_not_called()

    def test_unknown_or_manual_revision_never_reaches_chat(self):
        rag=StudioRAG(self.store,self.chat,manifest=self.manifest)
        for key,value in [('corpus','manual'),('source_sha256','changed'),('source_id','manufacturer-manual')]:
            hit=deepcopy(self.hit);hit['metadata'][key]=value
            with patch('app.rag.generate.search',return_value=[hit]),self.assertRaises(ChatError):
                rag.answer('question')
        self.chat.complete.assert_not_called()

    def test_hallucinated_citations_urls_and_answer_schema_rejected(self):
        rag=StudioRAG(self.store,self.chat,manifest=self.manifest)
        outputs=[{'answer':'Unsupported [S99]','answerable':True,'citation_ids':['S99']},
                 {'answer':'Unsupported','answerable':True,'citation_ids':[]},
                 {'answer':'See https://invented.invalid','answerable':True,'citation_ids':['S1']},
                 {'answer':'Wrong [S2]','answerable':True,'citation_ids':['S1']},
                 {'answer':'Missing','answerable':1,'citation_ids':['S1']}]
        for output in outputs:
            self.chat.complete.return_value=output
            with patch('app.rag.generate.search',return_value=[self.hit]),self.assertRaises(ChatError):rag.answer('question')

    def test_explicit_abstention(self):
        rag=StudioRAG(self.store,self.chat,manifest=self.manifest)
        self.chat.complete.return_value={'answer':'Exact hardware specifications are absent.','answerable':False,'citation_ids':[]}
        with patch('app.rag.generate.search',return_value=[self.hit]):
            result=rag.answer('Give an exact hardware specification')
        self.assertFalse(result['answerable']);self.assertEqual(result['citations'],[])

    def test_nebius_transport_with_real_schema_and_no_network(self):
        seen=[]
        def handler(request):
            seen.append(request.url.path)
            if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'verified-test-model'}]})
            payload=json.loads(request.content)
            self.assertEqual(payload['model'],'verified-test-model')
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'answer':'Evidence [S1]','answerable':True,'citation_ids':['S1']})}}]})
        settings=ChatSettings(api_key='secret-test',model='verified-test-model')
        client=httpx.Client(transport=httpx.MockTransport(handler))
        chat=NebiusChat(settings,client=client)
        self.assertTrue(chat.complete([{'role':'user','content':'test'}])['answerable'])
        self.assertEqual(seen,['/v1/models','/v1/chat/completions'])
        self.assertNotIn('secret-test',repr(settings))

    def test_nebius_errors_and_bounded_retries(self):
        calls=[]
        def handler(request):
            calls.append(1)
            return httpx.Response(503,json={'error':'sensitive response'})
        chat=NebiusChat(ChatSettings(api_key='secret'),client=httpx.Client(transport=httpx.MockTransport(handler)),sleep=Mock())
        with self.assertRaises(ChatError) as error:chat.complete([])
        self.assertEqual(len(calls),3);self.assertNotIn('sensitive response',str(error.exception))
        with patch('app.config.dotenv_values',return_value={}),patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):ChatSettings.from_env()

    def test_api_health_and_mocked_question(self):
        from app.main import app
        client=TestClient(app)
        self.assertEqual(client.get('/health').status_code,200)
        with patch('app.main.get_rag_service') as factory:
            factory.return_value.answer.return_value={'answer':'Test [S1]','answerable':True,'citations':[]}
            response=client.post('/ask',json={'question':'What is monitoring?'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['answerable'])
        self.assertEqual(client.post('/ask',json={'question':'','strategy':'D'}).status_code,422)
