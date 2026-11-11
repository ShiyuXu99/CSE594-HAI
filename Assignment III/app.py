import os
import secrets
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, render_template, request, session, abort, redirect, url_for
from dotenv import load_dotenv
from database import get_connection
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT/'.env', interpolate=False)
secret = os.environ.get('SECRET_KEY')
if not secret:
    if os.environ.get('RENDER') == 'true':
        raise RuntimeError('Set SECRET_KEY for deployment.')
    path = ROOT/'.session-secret'
    if not path.exists():
        try:
            with path.open('x') as file: file.write(secrets.token_hex(32))
            path.chmod(0o600)
        except FileExistsError: pass
    secret = path.read_text().strip()
app = Flask(__name__)
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_NAME='hai_a3', SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('RENDER')=='true',
                  MAX_CONTENT_LENGTH=8192)
LABELS = {'angry','happy','sad','surprise'}
CONDITIONS = {'baseline','ai'}
@contextmanager
def db():
    conn=get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur: yield cur
    finally: conn.close()
def participant(cur,user_name):
    pid=session.get('participant_id')
    if pid:
        cur.execute('SELECT participant_id FROM a3.participants WHERE participant_id=%s FOR UPDATE',(pid,))
        if cur.fetchone():
            cur.execute('UPDATE a3.participants SET user_name=%s WHERE participant_id=%s',(user_name,pid))
            return pid
    pid=str(uuid.uuid4())
    cur.execute('INSERT INTO a3.participants(participant_id,user_name) VALUES (%s,%s)',(pid,user_name))
    session['participant_id']=pid
    session.permanent=True
    return pid
def owned(cur,condition):
    pid=session.get('participant_id')
    if not pid: return None
    cur.execute('SELECT * FROM a3.sessions WHERE participant_id=%s AND condition=%s FOR UPDATE',(pid,condition))
    return cur.fetchone()
def state(cur,s):
    cur.execute('SELECT user_name FROM a3.participants WHERE participant_id=%s',(s['participant_id'],))
    name=cur.fetchone()['user_name']
    result={'user_name':name,'session_id':str(s['session_id']),'participant_id':str(s['participant_id']),
            'condition':s['condition'],'completed':s['status']=='completed',
            'attention_passed':s['attention_passed'],'total':20,'rating_scale':s['rating_scale']}
    cur.execute('SELECT count(*) AS n FROM a3.trials WHERE session_id=%s AND selected_label IS NOT NULL',(s['session_id'],))
    result['answered']=cur.fetchone()['n']
    result['attention_due'] = not s['attention_passed'] and result['answered'] >= s['attention_after']
    if result['attention_due']:
        cur.execute('UPDATE a3.sessions SET attention_shown_at=COALESCE(attention_shown_at,now()) WHERE session_id=%s',(s['session_id'],))
    if result['completed'] or result['attention_due']: return result
    cur.execute("""SELECT t.image_id,t.position,t.shown_at,i.filename
        FROM a3.trials t JOIN a3.images i USING(image_id)
        WHERE t.session_id=%s AND t.selected_label IS NULL ORDER BY t.position LIMIT 1""",(s['session_id'],))
    trial=cur.fetchone()
    if trial:
        cur.execute('UPDATE a3.trials SET shown_at=COALESCE(shown_at,now()) WHERE session_id=%s AND image_id=%s',
                    (s['session_id'],trial['image_id']))
        result['trial']={'image_id':trial['image_id'],'position':trial['position'],
                         'image_url':url_for('static',filename='study_images/'+trial['filename'])}
    return result
@app.before_request
def csrf():
    if (request.path.startswith('/api/') or request.path.startswith('/admin')) and request.method=='POST':
        if not secrets.compare_digest(session.get('csrf','').encode(),(request.headers.get('X-CSRF-Token') or request.form.get('csrf_token','')).encode()) or not session.get('csrf'):
            return jsonify(error='Your session expired. Refresh and try again.'),403
@app.after_request
def headers(response):
    if request.path.startswith(('/api/','/admin')) or request.path in ('/X','/Y','/baseline','/ai'):
        response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response
@app.errorhandler(psycopg2.Error)
def database_error(error):
    return jsonify(error='The study database is unavailable. Please try again; saved answers are kept.'),503
@app.get('/')
def home(): return redirect('/Y')
@app.get('/<condition>')
def study(condition):
    if condition in CONDITIONS:
        return redirect('/X' if condition=='ai' else '/Y')
    condition={'X':'ai','Y':'baseline'}.get(condition)
    if condition not in CONDITIONS: abort(404)
    session.setdefault('csrf',secrets.token_hex(32))
    return render_template('index.html',condition=condition,csrf_token=session['csrf'],allow_retest=os.environ.get('ALLOW_RETEST')=='true')
@app.route('/api/<condition>/state',methods=['GET'])
def get_state(condition):
    if condition not in CONDITIONS: abort(404)
    if not session.get('participant_id'): return jsonify(study=None)
    with db() as cur:
        s=owned(cur,condition)
        return jsonify(study=state(cur,s) if s else None)
@app.post('/api/<condition>/retest')
def retest(condition):
    if condition not in CONDITIONS or os.environ.get('ALLOW_RETEST')!='true': abort(404)
    # Start a fresh participant identity without deleting responses or signing out admin.
    session.pop('participant_id',None)
    return jsonify(study=None)

@app.post('/api/<condition>/start')
def start(condition):
    if condition not in CONDITIONS: abort(404)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('user_name'),str) or not 1<=len(data['user_name'].strip())<=100:
        return jsonify(error='Enter a user name between 1 and 100 characters.'),400
    with db() as cur:
        pid=participant(cur,data['user_name'].strip())
        s=owned(cur,condition)
        if not s:
            sid=str(uuid.uuid4())
            cur.execute('INSERT INTO a3.sessions(session_id,participant_id,condition,attention_after) VALUES (%s,%s,%s,%s)',(sid,pid,condition,secrets.randbelow(19)+1))
            # Five randomly sampled images per category; exclude images assigned in the other condition.
            chosen=[]
            for label in sorted(LABELS):
                cur.execute("""SELECT i.image_id FROM a3.images i WHERE true_label=%s AND NOT EXISTS
                    (SELECT 1 FROM a3.trials t JOIN a3.sessions s USING(session_id)
                     WHERE s.participant_id=%s AND t.image_id=i.image_id) ORDER BY random() LIMIT 5""",(label,pid))
                chosen.extend(r['image_id'] for r in cur.fetchall())
            if len(chosen)!=20: raise psycopg2.DatabaseError('Insufficient study images')
            secrets.SystemRandom().shuffle(chosen)
            for position,iid in enumerate(chosen,1):
                cur.execute('INSERT INTO a3.trials(session_id,image_id,position) VALUES (%s,%s,%s)',(sid,iid,position))
            s=owned(cur,condition)
        return jsonify(study=state(cur,s))
@app.post('/api/<condition>/attention')
def attention(condition):
    if condition not in CONDITIONS: abort(404)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='Choose an answer.'),400
    with db() as cur:
        s=owned(cur,condition)
        if not s: return jsonify(error='Start the study first.'),400
        if not isinstance(data.get('answer'),str) or data['answer'] not in LABELS:
            return jsonify(error='Choose one of the four options.'),400
        ms=data.get('active_ms',0)
        if type(ms) is not int or not 0<=ms<=86400000: return jsonify(error='Invalid response time.'),400
        if not s['attention_passed']:
            cur.execute('SELECT count(*) AS n FROM a3.trials WHERE session_id=%s AND selected_label IS NOT NULL',(s['session_id'],))
            if cur.fetchone()['n'] < s['attention_after'] or s['attention_shown_at'] is None:
                return jsonify(error='The attention check is not currently due.'),409
            passed=data.get('answer')=='surprise'
            cur.execute('INSERT INTO a3.attention_responses(session_id,selected_label,correct,active_ms) VALUES (%s,%s,%s,%s)',(s['session_id'],data['answer'],passed,ms))
            cur.execute('UPDATE a3.sessions SET attention_attempts=attention_attempts+1, attention_passed=%s WHERE session_id=%s',(passed,s['session_id']))
            if not passed:
                return jsonify(error='Please read the instruction: select Surprise for this check. You can try again.'),400
        return jsonify(study=state(cur,owned(cur,condition)))
@app.post('/api/<condition>/answer')
def answer(condition):
    if condition not in CONDITIONS: abort(404)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('label'),str) or data.get('label') not in LABELS or not isinstance(data.get('image_id'),str):
        return jsonify(error='Choose one of the four expressions.'),400
    confidence=data.get('trial_confidence')
    if type(confidence) is not int or not 1<=confidence<=5: return jsonify(error='Choose a confidence rating from 1 to 5.'),400
    ms=data.get('active_ms')
    if type(ms) is not int or not 0<=ms<=86400000: return jsonify(error='Invalid response time. Refresh and retry.'),400
    with db() as cur:
        s=owned(cur,condition)
        if not s: return jsonify(error='Start the study first.'),400
        if data.get('session_id')!=str(s['session_id']): return jsonify(error='This study session has changed. Refresh.'),409
        cur.execute('SELECT * FROM a3.trials WHERE session_id=%s AND image_id=%s',(s['session_id'],data['image_id']))
        t=cur.fetchone()
        if not t: return jsonify(error='Image not assigned to this session.'),400
        if t['selected_label']:
            if t['selected_label']!=data['label']: return jsonify(error='This answer was already saved.'),409
        else:
            if condition=='ai' and (not t['ai_displayed_at'] or not t['ai_inference_id'] or data.get('inference_id')!=str(t['ai_inference_id'])):
                return jsonify(error='Wait for the AI suggestion to finish loading before saving.'),409
            cur.execute('SELECT count(*) AS n FROM a3.trials WHERE session_id=%s AND selected_label IS NOT NULL',(s['session_id'],))
            if not s['attention_passed'] and cur.fetchone()['n'] >= s['attention_after']:
                return jsonify(error='Complete the attention check before continuing.'),409
            cur.execute('SELECT min(position) AS n FROM a3.trials WHERE session_id=%s AND selected_label IS NULL',(s['session_id'],))
            if t['position']!=cur.fetchone()['n'] or t['shown_at'] is None:
                return jsonify(error='Please answer the current image first.'),409
            cur.execute('UPDATE a3.trials SET selected_label=%s,submitted_at=now(),active_ms=%s,trial_confidence=%s WHERE session_id=%s AND image_id=%s',
                        (data['label'],ms,confidence,s['session_id'],data['image_id']))
        return jsonify(study=state(cur,s))
def current_ai_trial(cur,data):
    s=owned(cur,'ai')
    if not s or data.get('session_id')!=str(s['session_id']): return None,None
    view=state(cur,s)
    if not view.get('trial') or view['trial']['image_id']!=data.get('image_id'): return None,None
    cur.execute('SELECT filename FROM a3.images WHERE image_id=%s',(data['image_id'],))
    return s,cur.fetchone()

def predict_image(path):
    from inference import predict_image as infer
    return infer(path)

@app.post('/api/ai/predict')
def predict():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='Invalid inference request.'),400
    with db() as cur:
        s,image=current_ai_trial(cur,data)
        if not s: return jsonify(error='This image is not the current AI trial.'),409
        inference_id=str(uuid.uuid4())
        requested_at=datetime.now(timezone.utc)
        try:
            output=predict_image(ROOT/'static/study_images'/image['filename'])
        except Exception:
            app.logger.exception('Real-time inference failed')
            cur.execute("""INSERT INTO a3.inference_events(inference_id,session_id,image_id,status,requested_at,error_code)
                VALUES (%s,%s,%s,'failed',%s,'inference_unavailable')""",(inference_id,s['session_id'],data['image_id'],requested_at))
            return jsonify(error='AI is temporarily unavailable. Please retry.'),503
        cur.execute("""INSERT INTO a3.inference_events(inference_id,session_id,image_id,status,requested_at,
            prediction,confidence,scores,model_version,latency_ms)
            VALUES (%s,%s,%s,'success',%s,%s,%s,%s::jsonb,%s,%s)""",
            (inference_id,s['session_id'],data['image_id'],requested_at,output['prediction'],output['confidence'],
             json.dumps(output['scores']),output['model_version'],output['latency_ms']))
        return jsonify(output={'inference_id':inference_id,'image_id':data['image_id'],**output})

@app.post('/api/ai/displayed')
def displayed():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='Invalid display receipt.'),400
    try: inference_id=str(uuid.UUID(data.get('inference_id','')))
    except (ValueError,TypeError,AttributeError): return jsonify(error='Invalid display receipt.'),400
    with db() as cur:
        s,image=current_ai_trial(cur,data)
        if not s: return jsonify(error='This image is not the current AI trial.'),409
        cur.execute("""SELECT * FROM a3.inference_events WHERE inference_id=%s AND session_id=%s AND image_id=%s AND status='success'""",
                    (inference_id,s['session_id'],data['image_id']))
        event=cur.fetchone()
        if not event: return jsonify(error='AI output not found.'),409
        cur.execute('UPDATE a3.inference_events SET displayed_at=COALESCE(displayed_at,clock_timestamp()) WHERE inference_id=%s',(inference_id,))
        cur.execute("""UPDATE a3.trials SET ai_prediction_shown=%s,ai_confidence_shown=%s,
            ai_output_source='synchronous',ai_model_version=%s,ai_generated_at=%s,
            ai_displayed_at=COALESCE((SELECT displayed_at FROM a3.inference_events WHERE inference_id=%s),clock_timestamp()),ai_inference_id=%s
            WHERE session_id=%s AND image_id=%s""",
            (event['prediction'],event['confidence'],event['model_version'],event['generated_at'],inference_id,inference_id,s['session_id'],data['image_id']))
        return jsonify(ok=True)

@app.get('/health')
def health(): return jsonify(status='ok')

@app.post('/api/<condition>/finish')
def finish(condition):
    if condition not in CONDITIONS: abort(404)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or type(data.get('workload')) is not int or not 1<=data['workload']<=7:
        return jsonify(error='Choose a mental demand rating.'),400
    comments=data.get('comments','')
    if not isinstance(comments,str) or len(comments)>2000: return jsonify(error='Comments must be at most 2,000 characters.'),400
    with db() as cur:
        s=owned(cur,condition)
        if not s: return jsonify(error='Study session not found.'),400
        if data['workload'] > s['rating_scale']:
            return jsonify(error='Choose a rating within the displayed scale.'),400
        cur.execute('SELECT count(*) AS n FROM a3.trials WHERE session_id=%s AND selected_label IS NOT NULL',(s['session_id'],))
        if cur.fetchone()['n']!=20 or not s['attention_passed']: return jsonify(error='Complete all images first.'),400
        if s['status']!='completed':
            cur.execute("""UPDATE a3.sessions SET status='completed',completed_at=now(),workload=%s,comments=%s WHERE session_id=%s""",
                        (data['workload'],comments.strip(),s['session_id']))
        return jsonify(study=state(cur,owned(cur,condition)))
from admin import register_admin
register_admin(app, lambda: db())

if __name__=='__main__': app.run(port=5003,debug=False)
