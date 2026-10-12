import os
import secrets
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from flask import Flask, jsonify, render_template, request, session, abort
from dotenv import load_dotenv

from database import get_connection

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', interpolate=False)
secret = os.environ.get('SECRET_KEY')
if not secret:
    # Keep local sessions stable across restarts. Set SECRET_KEY on Render.
    secret_file = ROOT / '.session-secret'
    if not secret_file.exists():
        try:
            with secret_file.open('x') as file:
                file.write(secrets.token_hex(32))
            secret_file.chmod(0o600)
        except FileExistsError:
            pass
    secret = secret_file.read_text().strip()

app = Flask(__name__)
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('RENDER') == 'true',
                  MAX_CONTENT_LENGTH=4096)
EMOTIONS = {'anger', 'fear', 'joy', 'love', 'sadness', 'surprise'}


@contextmanager
def db_cursor():
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                yield cursor
    finally:
        connection.close()


def task_state(cursor, participant_id):
    cursor.execute("""SELECT task_id, completed_at FROM tasks WHERE participant_id=%s
                      ORDER BY started_at DESC, task_id DESC LIMIT 1""", (participant_id,))
    task = cursor.fetchone()
    if task is None:
        return None
    task_id = str(task[0])
    cursor.execute("""SELECT a.tweet_id,t.text,a.position,a.selected_label
                      FROM annotations a JOIN tweets t USING(tweet_id)
                      WHERE a.task_id=%s ORDER BY a.position""", (task_id,))
    return {'participant_id': participant_id, 'task_id': task_id,
            'completed': task[1] is not None,
            'tweets': [dict(zip(('tweet_id','text','position','selected_label'), row))
                       for row in cursor.fetchall()]}


@app.route('/')
def home():
    session.setdefault('csrf_token', secrets.token_hex(32))
    return render_template('index.html', csrf_token=session['csrf_token'], local_testing=local_testing())


def local_testing():
    return (app.debug and not os.environ.get('RENDER')
            and request.remote_addr in ('127.0.0.1', '::1')
            and request.host.split(':')[0] in ('127.0.0.1', 'localhost'))


@app.post('/api/retest')
def retest():
    if not local_testing():
        abort(404)
    session.pop('participant_id', None)
    return jsonify(task=None)


@app.before_request
def protect_writes():
    if request.path.startswith('/api/') and request.method == 'POST':
        expected = session.get('csrf_token', '')
        supplied = request.headers.get('X-CSRF-Token', '')
        if not expected or not secrets.compare_digest(expected, supplied):
            return jsonify(error='Your session expired. Refresh the page and try again.'), 403


@app.after_request
def private_responses(response):
    if request.path == '/' or request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(psycopg2.Error)
def database_error(error):
    return jsonify(error='We could not reach the database. Your progress is safe; please try again.'), 503


@app.get('/api/task')
def current_task():
    participant_id = session.get('participant_id')
    if not participant_id:
        return jsonify(task=None)
    with db_cursor() as cursor:
        state = task_state(cursor, participant_id)
    if state is None:
        session.pop('participant_id', None)
    return jsonify(task=state)


@app.post('/api/start')
def start_task():
    with db_cursor() as cursor:
        participant_id = session.get('participant_id')
        if participant_id:
            cursor.execute('SELECT participant_id FROM participants WHERE participant_id=%s FOR UPDATE', (participant_id,))
            if not cursor.fetchone():
                participant_id = None
        if not participant_id:
            participant_id = str(uuid.uuid4())
            cursor.execute('INSERT INTO participants(participant_id) VALUES (%s)', (participant_id,))
        state = task_state(cursor, participant_id)
        if state and not state['completed']:
            return jsonify(task=state)
        # A repeated start request for an old round must not create another round.
        data = request.get_json(silent=True) or {}
        if state and (not isinstance(data, dict) or data.get('previous_task_id') != state['task_id']):
            return jsonify(task=state)
        cursor.execute("""SELECT tweet_id FROM tweets t WHERE NOT EXISTS (
            SELECT 1 FROM annotations a WHERE a.participant_id=%s AND a.tweet_id=t.tweet_id)
            ORDER BY random() LIMIT 5""", (participant_id,))
        tweets = cursor.fetchall()
        if len(tweets) < 5:
            cursor.execute('SELECT tweet_id FROM tweets ORDER BY random() LIMIT 5')
            tweets = cursor.fetchall()
        if len(tweets) != 5:
            raise psycopg2.DatabaseError('Insufficient task data')
        task_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO tasks(task_id,participant_id) VALUES (%s,%s)', (task_id,participant_id))
        for position, (tweet_id,) in enumerate(tweets, 1):
            cursor.execute('INSERT INTO annotations(participant_id,task_id,tweet_id,position) VALUES (%s,%s,%s,%s)',
                           (participant_id,task_id,tweet_id,position))
        state = task_state(cursor, participant_id)
    session['participant_id'] = participant_id
    session.pop('seen_tweet_ids', None)
    session.permanent = True
    return jsonify(task=state)


@app.post('/api/answer')
def save_answer():
    participant_id = session.get('participant_id')
    if not participant_id:
        return jsonify(error='Start the task before submitting an answer.'), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('label'), str) or data['label'] not in EMOTIONS or not isinstance(data.get('tweet_id'), str) or not isinstance(data.get('task_id'), str):
        return jsonify(error='Choose one of the six emotion labels.'), 400
    with db_cursor() as cursor:
        cursor.execute('SELECT participant_id FROM participants WHERE participant_id = %s FOR UPDATE', (participant_id,))
        if not cursor.fetchone():
            return jsonify(error='Your task was not found. Refresh the page.'), 404
        state = task_state(cursor, participant_id)
        if not state or data['task_id'] != state['task_id']:
            return jsonify(error='This round is no longer current. Refresh to continue.'), 409
        task_id = state['task_id']
        cursor.execute('SELECT selected_label, position FROM annotations WHERE task_id = %s AND tweet_id = %s',
                       (task_id, data['tweet_id']))
        annotation = cursor.fetchone()
        if not annotation:
            return jsonify(error='This tweet is not part of your task.'), 400
        if annotation[0] is not None:
            if annotation[0] != data['label']:
                return jsonify(error='This answer has already been saved. Refresh to continue.'), 409
        else:
            cursor.execute('SELECT MIN(position) FROM annotations WHERE task_id = %s AND selected_label IS NULL', (task_id,))
            if cursor.fetchone()[0] != annotation[1]:
                return jsonify(error='Please label the current tweet first.'), 409
            cursor.execute('UPDATE annotations SET selected_label = %s, submitted_at = CURRENT_TIMESTAMP WHERE task_id = %s AND tweet_id = %s',
                           (data['label'], task_id, data['tweet_id']))
            cursor.execute('''UPDATE tasks SET completed_at = CURRENT_TIMESTAMP
                              WHERE task_id = %s AND completed_at IS NULL
                              AND (SELECT COUNT(*) FROM annotations WHERE task_id = %s AND selected_label IS NOT NULL) = 5''',
                           (task_id, task_id))
        state = task_state(cursor, participant_id)
    return jsonify(task=state)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
