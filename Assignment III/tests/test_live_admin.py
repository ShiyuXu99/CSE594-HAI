"""Opt-in PostgreSQL integration checks; all writes are rolled back. Run manually."""
import os,sys,time
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
root=Path(__file__).resolve().parents[1]
load_dotenv(root/'.env' if (root/'.env').exists() else root.parent/'Assignment I/.env',interpolate=False)
os.environ['SECRET_KEY']='live-rollback-test-secret'
os.environ['ADMIN_USERNAME']='admin'
os.environ['ADMIN_PASSWORD_HASH']=generate_password_hash('test-rollback-password',method='pbkdf2:sha256:600000')
sys.path.insert(0,str(root))
import app
from psycopg2.extras import RealDictCursor
conn=app.get_connection()
@contextmanager
def db():
    with conn.cursor(cursor_factory=RealDictCursor) as cur:yield cur
app.db=db;app.app.config['TESTING']=True
try:
    with conn.cursor() as cur:
        for migration in sorted((root/'migrations').glob('*.sql')):cur.execute(migration.read_text())
    client=app.app.test_client();client.get('/Y')
    with client.session_transaction() as s:token=s['csrf']
    headers={'X-CSRF-Token':token}
    assert client.get('/admin').status_code==302
    assert client.get('/admin/export/trials.csv').status_code==302
    assert client.post('/admin/login',data={'username':'admin','password':'test-rollback-password'}).status_code==403
    participant_id=None
    for condition,slot in [('baseline',1),('ai',19)]:
        app.secrets.randbelow=lambda n:slot-1
        def post(action,data):return client.post('/api/'+condition+'/'+action,json=data,headers=headers)
        s=post('start',{'user_name':'Test participant'}).json['study'];sid=s['session_id'];participant_id=s['participant_id']
        assert s['rating_scale']==5 and s['trial'] and not s['attention_due']
        assert post('attention',{'answer':'surprise'}).status_code==409
        for i in range(20):
            if s['attention_due']:
                assert i==slot and 'trial' not in s
                assert client.get('/api/'+condition+'/state').json['study']==s
                assert post('attention',{'answer':'angry','active_ms':1000}).status_code==400
                s=post('attention',{'answer':'surprise','active_ms':1500}).json['study']
            t=s['trial'];assert 'ai_prediction' not in t
            body={'session_id':sid,'image_id':t['image_id'],'label':'happy','active_ms':1300}
            if condition=='ai':
                request={'session_id':sid,'image_id':t['image_id']}
                output=post('predict',request).json['output']
                assert post('displayed',{**request,'inference_id':output['inference_id']}).status_code==200
                body['inference_id']=output['inference_id']
            r=post('answer',body);assert r.status_code==200,r.json;s=r.json['study']
        assert post('finish',{'workload':6,'confidence':5}).status_code==400
        assert post('finish',{'workload':3,'confidence':4,'comments':'=TEST <script>alert(1)</script>'}).json['study']['completed']
    client.get('/admin/login')
    assert client.post('/admin/login',data={'csrf_token':token,'username':'admin','password':'wrong'}).status_code==401
    assert client.post('/admin/login',data={'csrf_token':token,'username':'管理员','password':'test-rollback-password'}).status_code==401
    response=client.post('/admin/login',data={'csrf_token':token,'username':'admin','password':'test-rollback-password'});assert response.status_code==302
    for path in ['/admin','/admin/?q='+participant_id,'/admin/?condition=baseline&status=completed','/admin/?page=2','/admin/participants/'+participant_id]:
        response=client.get(path);assert response.status_code==200,(path,response.status_code)
        assert response.headers['Cache-Control']=='no-store'
    detail=client.get('/admin/participants/'+participant_id).text
    assert '&lt;script&gt;' in detail and '<script>alert' not in detail
    for kind in ['sessions','trials','attention','inference']:
        response=client.get('/admin/export/'+kind+'.csv');assert response.status_code==200
        if kind=='sessions':assert "'=TEST" in response.text
    assert client.get('/admin/participants/invalid').status_code==404
    with client.session_transaction() as s:s['admin_at']=time.time()-3601
    assert client.get('/admin').status_code==302
    # Rate limiting and logout use the same persistent attempt records as production.
    with client.session_transaction() as s:token=s['csrf']
    for i in range(8):
        assert client.post('/admin/login',data={'csrf_token':token,'username':'admin','password':'wrong'}).status_code==401
    assert client.post('/admin/login',data={'csrf_token':token,'username':'admin','password':'test-rollback-password'}).status_code==429
    print('PASS: PostgreSQL migration; full 40-image flow; first/last possible random check slots; failed check persistence; 5-point validation; protected admin dashboard/detail/exports; search/filters; CSRF; wrong credentials; session expiration; rate limit; HTML/CSV escaping. ALL changes rolled back.')
finally:
    conn.rollback();conn.close()
