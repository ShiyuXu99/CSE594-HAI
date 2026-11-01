"""Read-only study administration. Credentials remain in server environment."""
import csv
import io
import os
import secrets
import time
import uuid
import hashlib
import hmac
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, session, render_template, redirect, url_for, abort, Response
from werkzeug.security import check_password_hash

def register_admin(app, db):
    bp = Blueprint('admin', __name__, url_prefix='/admin')
    def credentials():
        return os.environ.get('ADMIN_USERNAME','admin'), os.environ.get('ADMIN_PASSWORD_HASH','')
    def fingerprint():
        return hashlib.sha256(credentials()[1].encode()).hexdigest()
    def authenticated():
        return bool(credentials()[1]) and session.get('admin_auth') == fingerprint() and 0 <= time.time()-session.get('admin_at',0) < 3600
    def required(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not authenticated(): return redirect(url_for('admin.login'))
            return fn(*args,**kwargs)
        return wrapped
    @app.template_filter('duration')
    def duration(value):
        if value is None: return '—'
        seconds=max(0,float(value))
        return f'{int(seconds//60)}m {seconds%60:.1f}s' if seconds>=60 else f'{seconds:.1f}s'
    @app.template_filter('stamp')
    def stamp(value):
        return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if value else '—'
    @bp.route('/login', methods=['GET','POST'])
    def login():
        session.setdefault('csrf',secrets.token_hex(32))
        if authenticated(): return redirect(url_for('admin.dashboard'))
        error=None
        username,password_hash=credentials()
        if request.method=='POST':
            if not password_hash:
                return render_template('admin_login.html',error='Admin sign-in is not configured.',csrf_token=session['csrf']),503
            supplied=request.form.get('username','')
            password=request.form.get('password','')
            # Shared across workers; no raw IP or submitted password is stored.
            key=hmac.new(app.secret_key.encode(),b'admin-login',hashlib.sha256).hexdigest()
            with db() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(key,))
                cur.execute("SELECT count(*) AS n FROM a3.admin_login_attempts WHERE key=%s AND attempted_at > now() - interval '15 minutes'",(key,))
                if cur.fetchone()['n']>=8:
                    return render_template('admin_login.html',error='Too many failed attempts. Try again in 15 minutes.',csrf_token=session['csrf']),429
                valid=check_password_hash(password_hash,password) and secrets.compare_digest(supplied.encode(),username.encode())
                if not valid:
                    cur.execute('INSERT INTO a3.admin_login_attempts(key) VALUES (%s)',(key,))
                    error='Incorrect username or password.'
                else:
                    cur.execute('DELETE FROM a3.admin_login_attempts WHERE key=%s',(key,))
                    session['admin_auth']=fingerprint()
                    session['admin_at']=time.time()
                    session['csrf']=secrets.token_hex(32)
                    return redirect(url_for('admin.dashboard'))
        return render_template('admin_login.html',error=error,csrf_token=session['csrf']),401 if error else 200
    @bp.post('/logout')
    @required
    def logout():
        session.pop('admin_auth',None);session.pop('admin_at',None)
        session['csrf']=secrets.token_hex(32)
        return redirect(url_for('admin.login'))
    @bp.get('')
    @bp.get('/')
    @required
    def dashboard():
        query=request.args.get('q','').strip()[:100]
        condition=request.args.get('condition','')
        status=request.args.get('status','')
        page=max(1,min(request.args.get('page',1,type=int) or 1,100000))
        filters=[];params=[]
        if query:
            filters.append('(s.participant_id::text ILIKE %s OR s.session_id::text ILIKE %s OR p.user_name ILIKE %s)');params.extend(['%'+query+'%']*3)
        if condition in ('baseline','ai'): filters.append('s.condition=%s');params.append(condition)
        if status in ('active','completed'): filters.append('s.status=%s');params.append(status)
        where=' WHERE '+' AND '.join(filters) if filters else ''
        with db() as cur:
            cur.execute("SELECT count(DISTINCT participant_id) AS participants,count(*) AS sessions,count(*) FILTER(WHERE status='completed') AS completed FROM a3.sessions")
            totals=cur.fetchone()
            cur.execute('SELECT count(*) AS n FROM a3.sessions s JOIN a3.participants p USING(participant_id)'+where,params);count=cur.fetchone()['n']
            cur.execute("""SELECT s.*,p.user_name,COALESCE(t.answered,0) AS answered,COALESCE(t.correct,0) AS correct,t.active_seconds,
                extract(epoch FROM(COALESCE(s.completed_at,now())-s.started_at)) AS elapsed_seconds
                FROM a3.sessions s JOIN a3.participants p USING(participant_id) LEFT JOIN (
                SELECT session_id,count(selected_label) AS answered,
                count(*) FILTER(WHERE selected_label=i.true_label) AS correct,
                sum(active_ms)/1000.0 AS active_seconds
                FROM a3.trials JOIN a3.images i USING(image_id) GROUP BY session_id) t USING(session_id)"""+where+
                ' ORDER BY s.started_at DESC,s.session_id LIMIT 40 OFFSET %s',params+[(page-1)*40])
            rows=cur.fetchall()
        return render_template('admin_dashboard.html',rows=rows,totals=totals,count=count,page=page,
            query=query,condition=condition,status=status,csrf_token=session['csrf'])
    @bp.get('/participants/<participant_id>')
    @required
    def detail(participant_id):
        try: participant_id=str(uuid.UUID(participant_id))
        except ValueError: abort(404)
        with db() as cur:
            cur.execute('SELECT * FROM a3.participants WHERE participant_id=%s',(participant_id,))
            person=cur.fetchone()
            if not person: abort(404)
            cur.execute("SELECT *,extract(epoch FROM(COALESCE(completed_at,now())-started_at)) AS elapsed_seconds FROM a3.sessions WHERE participant_id=%s ORDER BY started_at,session_id",(participant_id,))
            studies=cur.fetchall()
            for study in studies:
                cur.execute("""SELECT t.*,i.filename,i.true_label,i.model_prediction,i.model_confidence,
                    (t.selected_label=i.true_label) AS correct,t.active_ms/1000.0 AS active_seconds,
                    extract(epoch FROM(t.submitted_at-t.shown_at)) AS elapsed_seconds
                    FROM a3.trials t JOIN a3.images i USING(image_id) WHERE session_id=%s ORDER BY position""",(study['session_id'],))
                study['trials']=cur.fetchall()
                study['answered']=sum(t['selected_label'] is not None for t in study['trials'])
                study['correct']=sum(t['correct'] is True for t in study['trials'])
                study['active_seconds']=sum((t['active_seconds'] or 0) for t in study['trials'])
                cur.execute('SELECT * FROM a3.attention_responses WHERE session_id=%s ORDER BY submitted_at,response_id',(study['session_id'],))
                study['checks']=cur.fetchall()
                cur.execute('SELECT * FROM a3.inference_events WHERE session_id=%s ORDER BY requested_at,inference_id',(study['session_id'],))
                study['inferences']=cur.fetchall()
        return render_template('admin_detail.html',person=person,studies=studies,csrf_token=session['csrf'])
    @bp.get('/export/<kind>.csv')
    @required
    def export(kind):
        queries={
            'sessions': 'SELECT p.user_name,s.* FROM a3.sessions s JOIN a3.participants p USING(participant_id) ORDER BY started_at,session_id',
            'trials': """SELECT p.user_name,s.participant_id,s.condition,s.status,t.*,i.true_label,i.model_prediction,i.model_confidence,
                (t.selected_label=i.true_label) AS correct,
                extract(epoch FROM(t.submitted_at-t.shown_at)) AS elapsed_seconds
                FROM a3.trials t JOIN a3.sessions s USING(session_id) JOIN a3.participants p USING(participant_id) JOIN a3.images i USING(image_id)
                ORDER BY s.started_at,t.position""",
            'inference': "SELECT p.user_name,s.participant_id,s.condition,e.* FROM a3.inference_events e JOIN a3.sessions s USING(session_id) JOIN a3.participants p USING(participant_id) ORDER BY requested_at,inference_id",
            'attention': """SELECT p.user_name,s.participant_id,s.condition,r.* FROM a3.attention_responses r
                JOIN a3.sessions s USING(session_id) JOIN a3.participants p USING(participant_id) ORDER BY submitted_at,response_id"""}
        if kind not in queries: abort(404)
        with db() as cur:
            cur.execute(queries[kind]);rows=cur.fetchall();columns=[c.name for c in cur.description]
        output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(columns)
        def safe(value):
            return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value
        for row in rows: writer.writerow([safe(row[column]) for column in columns])
        return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="a3-{kind}.csv"'})
    app.register_blueprint(bp)
