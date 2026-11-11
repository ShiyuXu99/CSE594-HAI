import os,sys,sqlite3,csv,re
from pathlib import Path
from contextlib import contextmanager
os.environ['SECRET_KEY']='local-test-only-secret'
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import app as module
conn=sqlite3.connect(':memory:')
conn.row_factory=sqlite3.Row
conn.executescript('''
CREATE TABLE images(image_id TEXT PRIMARY KEY,filename TEXT,true_label TEXT,model_prediction TEXT,model_confidence REAL);
CREATE TABLE participants(participant_id TEXT PRIMARY KEY,user_name TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE sessions(session_id TEXT PRIMARY KEY,participant_id TEXT,condition TEXT,status TEXT DEFAULT 'active',started_at TEXT DEFAULT CURRENT_TIMESTAMP,completed_at TEXT,attention_attempts INTEGER DEFAULT 0,attention_passed INTEGER DEFAULT 0,attention_after INTEGER,attention_shown_at TEXT,rating_scale INTEGER DEFAULT 5,workload INTEGER,confidence INTEGER,comments TEXT,UNIQUE(participant_id,condition));
CREATE TABLE attention_responses(response_id INTEGER PRIMARY KEY,session_id TEXT,selected_label TEXT,correct INTEGER,active_ms INTEGER,submitted_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE inference_events(inference_id TEXT PRIMARY KEY,session_id TEXT,image_id TEXT,status TEXT,requested_at TEXT,generated_at TEXT DEFAULT CURRENT_TIMESTAMP,displayed_at TEXT,prediction TEXT,confidence REAL,scores TEXT,model_version TEXT,latency_ms REAL,error_code TEXT);
CREATE TABLE trials(session_id TEXT,image_id TEXT,position INTEGER,shown_at TEXT,submitted_at TEXT,selected_label TEXT,trial_confidence INTEGER,active_ms INTEGER,ai_prediction_shown TEXT,ai_confidence_shown REAL,ai_output_source TEXT,ai_model_version TEXT,ai_generated_at TEXT,ai_displayed_at TEXT,ai_inference_id TEXT,PRIMARY KEY(session_id,image_id),UNIQUE(session_id,position));
''')
for r in csv.DictReader((root/'data/study_dataset.csv').open()):
    conn.execute('INSERT INTO images VALUES (?,?,?,?,?)',(r['image_id'],Path(r['input']).name,r['true_label'],r['model_prediction'],float(r['model_confidence'])))
conn.commit()
class Cursor:
    def execute(self,query,params=()):
        query=query.replace('a3.','').replace('%s','?').replace(' FOR UPDATE','').replace('::jsonb','').replace('clock_timestamp()','CURRENT_TIMESTAMP')
        query=re.sub(r'\bnow\(\)', 'CURRENT_TIMESTAMP',query)
        self.c=conn.execute(query,tuple(str(p) if not isinstance(p,(int,float,type(None))) else p for p in params))
    def fetchone(self):
        r=self.c.fetchone();return dict(r) if r else None
    def fetchall(self):return [dict(r) for r in self.c.fetchall()]
@contextmanager
def db():
    with conn:yield Cursor()
module.db=db
module.predict_image=lambda path: {'prediction':'happy','confidence':0.8,'scores':{'angry':0.05,'happy':0.8,'sad':0.1,'surprise':0.05},'model_version':'test-stub','latency_ms':2.0}
module.app.config['TESTING']=True
client=module.app.test_client()
page=client.get('/Y');assert page.status_code==200
assert client.get('/X').status_code==200
assert client.get('/bogus').status_code==404
assert client.post('/api/baseline/start',json={}).status_code==403
with client.session_transaction() as s:token=s['csrf']
headers={'X-CSRF-Token':token}
def post(condition,action,data):return client.post(f'/api/{condition}/{action}',json=data,headers=headers)
seen={}
for condition in ['baseline','ai']:
    s=post(condition,'start',{'user_name':'Test participant'}).json['study'];sid=s['session_id']
    assert post(condition,'start',{'user_name':'Test participant'}).json['study']['session_id']==sid
    assert not s['attention_passed'] and 'trial' in s
    assert s['rating_scale']==5
    assert post(condition,'attention',{'answer':'surprise'}).status_code==409
    assert post(condition,'finish',{'workload':4,'confidence':5}).status_code==400
    assigned=conn.execute('SELECT image_id FROM trials WHERE session_id=? ORDER BY position',(sid,)).fetchall()
    bad=post(condition,'answer',{'session_id':sid,'image_id':assigned[1][0],'label':'happy','trial_confidence':4,'active_ms':1000})
    assert bad.status_code==409
    seen[condition]=[]
    checks=0
    for i in range(20):
        if s['attention_due']:
            checks+=1
            assert 1<=s['answered']<=19 and 'trial' not in s
            assert client.get(f'/api/{condition}/state').json['study']==s
            assert post(condition,'answer',{'session_id':sid,'image_id':assigned[i][0],'label':'happy','trial_confidence':4,'active_ms':500}).status_code==409
            assert post(condition,'attention',{'answer':'angry','active_ms':800}).status_code==400
            s=post(condition,'attention',{'answer':'surprise','active_ms':1000}).json['study']
            assert s['attention_passed']
            assert post(condition,'attention',{'answer':'surprise'}).json['study']==s
        t=s['trial'];seen[condition].append(t['image_id'])
        assert 'ai_prediction' not in t
        assert not any(k in t for k in ['true_label','model_confidence','correct'])
        assert client.get(t['image_url']).status_code==200
        assert client.get(f'/api/{condition}/state').json['study']['trial']['image_id']==t['image_id']
        body={'session_id':sid,'image_id':t['image_id'],'label':'happy','trial_confidence':4,'active_ms':1200}
        if condition=='ai':
            assert post(condition,'answer',body).status_code==409
            request={'session_id':sid,'image_id':t['image_id']}
            output=post(condition,'predict',request).json['output']
            assert post(condition,'answer',{**body,'inference_id':output['inference_id']}).status_code==409
            assert post(condition,'displayed',{**request,'inference_id':output['inference_id']}).status_code==200
            body['inference_id']=output['inference_id']
        response=post(condition,'answer',body);assert response.status_code==200,response.json
        s=response.json['study']
        assert post(condition,'answer',body).json['study']==s
        conflict=post(condition,'answer',{**body,'label':'sad'});assert conflict.status_code==409
    assert checks==1
    assert post(condition,'finish',{'workload':6,'confidence':5}).status_code==400
    assert s['answered']==20 and 'trial' not in s and not s['completed']
    assert post(condition,'finish',{'workload':0,'confidence':4}).status_code==400
    s=post(condition,'finish',{'workload':4,'confidence':5,'comments':'Test'}).json['study'];assert s['completed']
    assert post(condition,'start',{'user_name':'Test participant'}).json['study']['completed']
    assert post(condition,'finish',{'workload':1,'confidence':1}).json['study']['completed']
    assert conn.execute('SELECT workload FROM sessions WHERE session_id=?',(sid,)).fetchone()[0]==4
    for label in ['happy','angry','sad','surprise']:
        assert conn.execute('SELECT count(*) FROM trials JOIN images USING(image_id) WHERE session_id=? AND true_label=?',(sid,label)).fetchone()[0]==5
assert not set(seen['baseline'])&set(seen['ai'])
assert conn.execute('SELECT count(*) FROM participants').fetchone()[0]==1
assert conn.execute('SELECT count(*) FROM trials WHERE ai_prediction_shown IS NOT NULL').fetchone()[0]==20
other=module.app.test_client();other.get('/Y')
with other.session_transaction() as s:other_token=s['csrf']
assert other.post('/api/baseline/answer',headers={'X-CSRF-Token':other_token},json={'session_id':sid,'image_id':seen['ai'][0],'label':'happy','trial_confidence':4,'active_ms':100}).status_code==400
assert conn.execute('SELECT count(*) FROM attention_responses').fetchone()[0]==4
assert conn.execute('SELECT count(*) FROM inference_events WHERE displayed_at IS NOT NULL').fetchone()[0]==20
assert conn.execute("SELECT count(*) FROM trials WHERE ai_output_source='synchronous' AND ai_confidence_shown=0.8").fetchone()[0]==20
assert client.get('/admin').status_code==302
assert client.get('/admin/export/trials.csv').status_code==302
other_headers={'X-CSRF-Token':other_token}
assert other.post('/api/baseline/start',headers=other_headers,json={'user_name':'   '}).status_code==400
same_name=other.post('/api/baseline/start',headers=other_headers,json={'user_name':'Test participant'}).json['study']
assert len({r[0] for r in conn.execute('SELECT participant_id FROM participants').fetchall()})==2
assert conn.execute('SELECT count(*) FROM participants WHERE user_name=?',('Test participant',)).fetchone()[0]==2
print('PASS: random in-task attention gating, early-submission protection, failed-attempt recording, 5-point scales; both complete 20-trial flows; baseline AI isolation; attention retries; balanced random sampling; cross-condition non-overlap; CSRF; foreign-session protection; refresh recovery; duplicate/conflicting answers; required questionnaires; completion idempotency; 40 image requests.')
print('Database adapter used SQLite in memory: PostgreSQL schema, permissions and network still require live verification.')
