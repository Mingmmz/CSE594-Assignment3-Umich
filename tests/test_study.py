"""End-to-end backend checks with temporary databases and packaged images."""
import base64
from concurrent.futures import ThreadPoolExecutor
import csv, io, json
from pathlib import Path
import tempfile, unittest, uuid
from app import create_app

class StudyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app(dict(TESTING=True,DATABASE_URL='',LOCAL_SQLITE_PATH=str(Path(self.temp.name)/'test.db'),ADMIN_PASSWORD='test-password',TRIALS_PER_SESSION=3))
        self.store=self.app.extensions['study_store'];self.store.initialize();self.client=self.app.test_client()
        self.admin={'Authorization':'Basic '+base64.b64encode(b'admin:test-password').decode()}
    def tearDown(self):
        self.temp.cleanup()
    def start(self,code='P01',condition='ai'):
        payload=dict(participant_code=code,condition=condition,consent=True,request_id=str(uuid.uuid4()))
        response=self.client.post('/api/start',json=payload)
        self.assertEqual(response.status_code,200,response.get_json())
        data=response.get_json();return data['state'],{'X-Session-Token':data['session_token']},payload
    def attention(self,h):
        r=self.client.post('/api/attention',headers=h,json={'answer':'image_evidence'});self.assertEqual(r.status_code,200);return r.get_json()
    def answer(self,state,h):
        trial=state['current'];key=trial['id']
        with self.client.get(trial['image_url'],headers=h) as image_response: self.assertEqual(image_response.status_code,200)
        self.assertEqual(self.client.post(f'/api/trials/{key}/ready',headers=h,json={'phase':'original'}).status_code,200)
        first={'label':'genuine','confidence':3}
        if state['condition']=='baseline':
            first.update(uncertain=True,comment='=test formula')
            self.assertEqual(self.client.get(f'/api/trials/{key}/gradcam',headers=h).status_code,403)
        r=self.client.post(f'/api/trials/{key}/initial',headers=h,json=first)
        self.assertEqual(r.status_code,200,r.get_json());review=r.get_json()
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json=first).status_code,200)
        if state['condition']=='baseline':
            self.assertEqual(review['completed_count'],state['completed_count']+1)
            self.assertTrue(review['current'] is None or review['current']['id']!=key)
            self.assertEqual(self.client.get(f'/api/trials/{key}/gradcam',headers=h).status_code,409)
            return review
        if state['condition']=='ai':
            with self.client.get(review['current']['ai']['gradcam_url'],headers=h) as cam_response: self.assertEqual(cam_response.status_code,200)
            self.assertEqual(self.client.post(f'/api/trials/{key}/ready',headers=h,json={'phase':'ai'}).status_code,200)
        else:
            self.assertNotIn('ai',review['current']);self.assertEqual(self.client.get(f'/api/trials/{key}/gradcam',headers=h).status_code,403)
        final={'label':'fake','confidence':4,'uncertain':True,'trust':2,'comment':'=test formula','reasons':['visual_details'] if state['condition']=='ai' else []}
        r=self.client.post(f'/api/trials/{key}/final',headers=h,json=final)
        self.assertEqual(r.status_code,200,r.get_json())
        self.assertEqual(self.client.post(f'/api/trials/{key}/final',headers=h,json=final).get_json(),r.get_json())
        return r.get_json()
    def test_conditions_repeat_runs_exports(self):
        sets=[]
        for i,condition in enumerate(['baseline','ai','ai']):
            state,h,_=self.start('Same-User',condition)
            self.assertEqual(state['sequence_no'],i+1);self.assertEqual(state['attempt_no'],2 if i==2 else 1)
            state=self.attention(h)
            with self.store.connect() as db:
                sets.append({r['item_id'] for r in db.all('SELECT item_id FROM trials WHERE session_id=?',(h['X-Session-Token'],))})
            while state['status']=='active':state=self.answer(state,h)
            self.assertEqual(state['status'],'survey')
            state=self.client.post('/api/survey',headers=h,json={'workload':4,'usefulness':5,'feedback':'done'}).get_json()
            self.assertEqual(state['status'],'completed');self.assertNotIn('completion_code',state)
        self.assertEqual(len(set.union(*sets)),9)
        with self.store.connect() as db:
            self.assertEqual(db.one('SELECT COUNT(*) AS n FROM sessions')['n'],3)
            self.assertEqual(db.one("SELECT COUNT(*) AS n FROM trials WHERE status='submitted'")['n'],9)
        rows=list(csv.DictReader(io.StringIO(self.client.get('/admin/export/trials.csv',headers=self.admin).get_data(as_text=True))))
        self.assertEqual(len(rows),9);self.assertEqual(sum(r['completed_rank']=='2' for r in rows),3)
        self.assertTrue(rows[0]['comment'].startswith("'="));self.assertIn(rows[0]['final_correct'],('0','1'))
        self.assertNotIn('session_id',rows[0]);self.assertNotIn('request_id',rows[0])
    def test_attention_and_answer_gates_no_label_leaks(self):
        state,h,_=self.start()
        with self.store.connect() as db:key=db.one('SELECT id FROM trials WHERE session_id=? ORDER BY position',(h['X-Session-Token'],))['id']
        self.assertEqual(self.client.get(f'/api/trials/{key}/image',headers=h).status_code,409)
        failed=self.client.post('/api/attention',headers=h,json={'answer':'outside_search'}).get_json()
        self.assertEqual(failed['status'],'attention');self.assertEqual(failed['attention_failures'],1)
        state=self.attention(h);key=state['current']['id']
        self.assertEqual(self.client.get(f'/api/trials/{key}/gradcam',headers=h).status_code,403)
        for secret in ('ground_truth','source_file','ai_prediction','gradcam','calibrated_fake_probability'):self.assertNotIn(secret,json.dumps(state))
        self.assertEqual(self.client.get('/data/study_manifest.json').status_code,404)
        self.assertEqual(self.client.get('/static/../data/study_manifest.json').status_code,404)
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json={'label':'fake','confidence':3}).status_code,409)
        self.assertEqual(self.client.post(f'/api/trials/{key}/final',headers=h,json={'label':'fake','confidence':3,'trust':2}).status_code,409)
    def test_start_retry_resume_and_session_isolation(self):
        state,h,payload=self.start();retry=self.client.post('/api/start',json=payload).get_json()
        self.assertEqual(retry['session_token'],h['X-Session-Token']);self.assertEqual(self.client.get('/api/state',headers=h).get_json(),state)
        _,h2,_=self.start('P02');state=self.attention(h)
        self.assertEqual(self.client.get(state['current']['image_url'],headers=h2).status_code,404)
        self.assertEqual(self.client.get('/api/state').status_code,401)
        self.assertEqual(self.client.post('/api/survey',headers=h,json={'workload':4,'usefulness':4}).status_code,409)
    def test_invalid_payloads_and_admin(self):
        for value in ([],None,'bad'):self.assertEqual(self.client.post('/api/start',data=json.dumps(value),content_type='application/json').status_code,400)
        state,h,_=self.start();state=self.attention(h);key=state['current']['id']
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json={'label':'fake','confidence':True}).status_code,400)
        self.assertEqual(self.client.post('/api/attention',headers={**h,'Origin':'https://outside.example'},json={'answer':'image_evidence'}).status_code,403)
        self.assertEqual(self.client.get('/admin').status_code,401);self.assertEqual(self.client.get('/admin',headers=self.admin).status_code,200)
        self.app.config['ADMIN_PASSWORD']='';self.assertEqual(self.client.get('/admin').status_code,503)
    def test_baseline_single_submission_retry_and_export(self):
        state,h,_=self.start(condition='baseline');state=self.attention(h);key=state['current']['id']
        payload={'label':'fake','confidence':4,'uncertain':True,'comment':'Logo was unclear.'}
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json=payload).status_code,409)
        with self.client.get(state['current']['image_url'],headers=h) as image_response:
            self.assertEqual(image_response.status_code,200)
        self.client.post(f'/api/trials/{key}/ready',headers=h,json={'phase':'original'})
        for changes in ({'confidence':True},{'uncertain':'yes'},{'comment':'x'*2001},{'trust':3},{'reasons':['visual_details']}):
            self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json={**payload,**changes}).status_code,400)
        result=self.client.post(f'/api/trials/{key}/initial',headers=h,json=payload)
        self.assertEqual(result.status_code,200);next_state=result.get_json()
        self.assertEqual(next_state['completed_count'],1);self.assertEqual(next_state['current']['position'],2)
        self.assertEqual(next_state['current']['status'],'pending');self.assertNotIn('ai',next_state['current'])
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json=payload).get_json(),next_state)
        self.assertEqual(self.client.post(f'/api/trials/{key}/initial',headers=h,json={**payload,'label':'genuine'}).get_json(),next_state)
        self.assertEqual(self.client.get('/api/state',headers=h).get_json(),next_state)
        with self.store.connect() as db:
            saved=db.one('SELECT * FROM trials WHERE id=?',(key,))
        self.assertEqual(saved['status'],'submitted');self.assertEqual(saved['initial_label'],'fake');self.assertEqual(saved['final_label'],'fake')
        self.assertEqual(saved['initial_confidence'],4);self.assertEqual(saved['final_confidence'],4)
        self.assertEqual(saved['initial_submitted_at'],saved['submitted_at']);self.assertEqual(saved['comment'],payload['comment'])
        self.assertEqual(saved['uncertain'],1);self.assertIsNone(saved['trust']);self.assertIsNone(saved['ai_revealed_at']);self.assertIsNone(saved['shown_prediction'])
        while next_state['status']=='active':next_state=self.answer(next_state,h)
        self.assertEqual(next_state['status'],'survey');self.assertEqual(next_state['completed_count'],3)
        rows=list(csv.DictReader(io.StringIO(self.client.get('/admin/export/trials.csv',headers=self.admin).get_data(as_text=True))))
        self.assertTrue(all(row['review_seconds']=='' for row in rows));self.assertTrue(all(row['initial_label']==row['final_label'] for row in rows))
    def test_baseline_legacy_review_can_resume(self):
        state,h,_=self.start(condition='baseline');state=self.attention(h);key=state['current']['id']
        old_stamp='2026-10-20T10:00:00.000+00:00'
        with self.store.connect() as db:
            db.execute("UPDATE trials SET status='review',image_ready_at=?,initial_label='genuine',initial_confidence=2,initial_submitted_at=? WHERE id=?",(old_stamp,old_stamp,key))
        resumed=self.client.get('/api/state',headers=h).get_json()
        self.assertEqual(resumed['current']['initial_label'],'genuine');self.assertNotIn('ai',resumed['current'])
        result=self.client.post(f'/api/trials/{key}/initial',headers=h,json={'label':'fake','confidence':4})
        self.assertEqual(result.status_code,200);self.assertEqual(result.get_json()['current']['position'],2)
        with self.store.connect() as db:saved=db.one('SELECT * FROM trials WHERE id=?',(key,))
        self.assertEqual(saved['initial_label'],'genuine');self.assertEqual(saved['initial_submitted_at'],old_stamp)
        self.assertEqual(saved['final_label'],'fake');self.assertEqual(saved['status'],'submitted')
    def test_condition_pages_describe_matching_flows(self):
        for path in ('/without-ai','/with-ai'):
            response=self.client.get(path);self.assertEqual(response.status_code,200)
            html=response.get_data(as_text=True)
            self.assertNotIn('second look',html.lower());self.assertNotIn('second time',html.lower())
            if path=='/without-ai':
                self.assertIn('class="step-indicator" hidden',html)
                self.assertIn('Submit once to save your answer',html)
            else:
                self.assertIn('Save your independent answer to see the AI',html)
    def test_trust_reasons_required_and_unchanged_option_consistent(self):
        state,h,_=self.start();state=self.attention(h);key=state['current']['id']
        self.client.post(f'/api/trials/{key}/ready',headers=h,json={'phase':'original'})
        self.client.post(f'/api/trials/{key}/initial',headers=h,json={'label':'genuine','confidence':3})
        self.client.post(f'/api/trials/{key}/ready',headers=h,json={'phase':'ai'})
        final={'label':'genuine','confidence':4,'trust':3,'reasons':[]}
        missing=self.client.post(f'/api/trials/{key}/final',headers=h,json=final)
        self.assertEqual(missing.status_code,400);self.assertIn('at least one',missing.get_json()['error'])
        final.update(label='fake',reasons=['unchanged_answer'])
        self.assertEqual(self.client.post(f'/api/trials/{key}/final',headers=h,json=final).status_code,400)
        final['label']='genuine'
        self.assertEqual(self.client.post(f'/api/trials/{key}/final',headers=h,json=final).status_code,200)
        with self.store.connect() as db:
            saved=db.one('SELECT reasons,initial_label,final_label FROM trials WHERE id=?',(key,))
        self.assertEqual(json.loads(saved['reasons']),['unchanged_answer']);self.assertEqual(saved['initial_label'],saved['final_label'])
    def test_render_https_proxy_origin_validation(self):
        from werkzeug.middleware.proxy_fix import ProxyFix
        self.app.wsgi_app=ProxyFix(self.app.wsgi_app,x_for=0,x_proto=1,x_host=0,x_port=0,x_prefix=0)
        payload=dict(participant_code='HTTPS',condition='ai',consent=True,request_id=str(uuid.uuid4()))
        response=self.client.post('/api/start',json=payload,headers={'Origin':'https://localhost','X-Forwarded-Proto':'https'})
        self.assertEqual(response.status_code,200,response.get_json())
    def test_skip_and_exhausted_pool(self):
        state,h,_=self.start(condition='baseline');state=self.attention(h)
        while state['status']=='active':state=self.client.post(f"/api/trials/{state['current']['id']}/skip",headers=h,json={'reason':'image_load_error'}).get_json()
        self.assertEqual(state['status'],'survey')
        with self.store.connect() as db:
            for i,item in enumerate(self.app.extensions['study_manifest']['items']):
                db.execute('INSERT INTO trials (id,session_id,position,item_id,status) VALUES (?,?,?,?,?) ON CONFLICT (session_id,item_id) DO NOTHING',(str(uuid.uuid4()),h['X-Session-Token'],i+100,item['item_id'],'skipped'))
        _,h2,_=self.start()
        with self.store.connect() as db:
            rows=db.all('SELECT * FROM trials WHERE session_id=?',(h2['X-Session-Token'],));self.assertEqual(len(rows),3);self.assertTrue(all(r['prior_exposures']>0 for r in rows))
    def test_concurrent_sessions_keep_runs_separate(self):
        def start_one(_):
            with self.app.test_client() as client:return client.post('/api/start',json=dict(participant_code='Concurrent',condition='ai',consent=True,request_id=str(uuid.uuid4()))).get_json()
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(start_one,range(4)))
        self.assertEqual(sorted(r['state']['attempt_no'] for r in results),[1,2,3,4])
        with self.store.connect() as db:self.assertEqual(db.one('SELECT COUNT(DISTINCT item_id) AS n FROM trials')['n'],12)

if __name__=='__main__':unittest.main()
