from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import csv
import hashlib
import io
import json
import os
import re
import secrets
import uuid

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from store import Store

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
BRANDS = {'adidas': 'Adidas', 'gucci': 'Gucci', 'lv': 'Louis Vuitton', 'nike': 'Nike', 'puma': 'Puma'}
LABELS = ('genuine', 'fake')
REASONS = {'relevant_regions', 'irrelevant_regions', 'confidence', 'visual_details', 'own_knowledge', 'unclear_image', 'unchanged_answer'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        abort(400, description=f'{name} must be between {low} and {high}.')
    return value

def text_value(value, max_length, name):
    if not isinstance(value, str) or len(value) > max_length:
        abort(400, description=f'{name} must be text with at most {max_length} characters.')
    return value.strip()

def label(value):
    if value not in LABELS:
        abort(400, description='Choose Genuine or Counterfeit.')
    return value

def elapsed(start, end):
    if not start or not end:
        return ''
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3)

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(DATABASE_URL=os.getenv('DATABASE_URL'), LOCAL_SQLITE_PATH=os.getenv('LOCAL_SQLITE_PATH'),
                      ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD', ''),
                      TRIALS_PER_SESSION=int(os.getenv('TRIALS_PER_SESSION', '10')),
                      MAX_CONTENT_LENGTH=32768, TRUST_RENDER_PROXY=os.getenv('TRUST_RENDER_PROXY') == '1')
    if config:
        app.config.update(config)
    if app.config['TRUST_RENDER_PROXY']:
        # Render terminates TLS at its proxy; trust only its one scheme header.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    store = Store(app.config)
    manifest = json.loads((BASE / 'data/study_manifest.json').read_text())
    items = {r['item_id']: r for r in manifest['items']}
    task_count = app.config['TRIALS_PER_SESSION']
    if not 1 <= task_count <= len(items):
        raise RuntimeError('TRIALS_PER_SESSION is outside the study pool size.')
    app.extensions.update(study_store=store, study_manifest=manifest)

    @app.cli.command('init-db')
    def init_db_command():
        """Initialize only the separate Assignment 3 tables."""
        store.initialize()
        print('Assignment 3 database initialized.')

    @app.cli.command('verify-data')
    def verify_data_command():
        """Verify the packaged images against their frozen checksums."""
        for name, expected in manifest['checksums'].items():
            path = BASE / 'data/stimuli' / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Dataset asset failed verification: {name}')
        print(f"Verified {len(items)} study items and {len(manifest['checksums'])} image assets.")

    @app.before_request
    def guard_requests():
        if request.method == 'POST':
            # JSON-only mutations and no CORS prevent cross-origin form submissions.
            if not request.is_json:
                abort(415, description='Send application/json.')
            if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
                abort(403, description='Please submit from this study website.')
            if not isinstance(request.get_json(silent=True), dict):
                abort(400, description='Expected a JSON object.')

    @app.after_request
    def secure_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith('/api/'):
            return jsonify(error=exc.description), exc.code
        return render_template('error.html', message=exc.description), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        # Do not log DB URIs, credentials, request tokens, or participant codes.
        app.logger.error('Study request failed (%s)', type(exc).__name__)
        message = 'The server could not save your request. Your previous work is preserved; please retry.'
        if request.path.startswith('/api/'):
            return jsonify(error=message), 503
        return render_template('error.html', message=message), 503

    def auth_session(db, lock=True):
        token = request.headers.get('X-Session-Token', '')
        if not token or len(token) > 80:
            abort(401, description='Start or resume your session on this browser.')
        session = db.one('SELECT * FROM sessions WHERE id=?', (token,), lock=lock)
        if session is None:
            abort(401, description='Session not found. Start a new run.')
        if session['dataset_version'] != manifest['version']:
            abort(409, description='The study dataset has changed. Please contact the researcher before continuing.')
        return session

    def current_trial(db, session):
        return db.one("SELECT * FROM trials WHERE session_id=? AND status IN ('pending','review') ORDER BY position LIMIT 1",
                      (session['id'],))

    def requested_trial(db, session, trial_id):
        row = db.one('SELECT * FROM trials WHERE id=? AND session_id=?', (trial_id, session['id']), lock=True)
        if row is None:
            abort(404, description='Trial not found in this session.')
        return row

    def require_current(db, session, row):
        current = current_trial(db, session)
        if session['status'] != 'active' or not current or current['id'] != row['id']:
            abort(409, description='Please finish the current trial first.')

    def finish_if_needed(db, session):
        if not current_trial(db, session):
            db.execute("UPDATE sessions SET status='survey' WHERE id=?", (session['id'],))
            session['status'] = 'survey'

    def state(db, session):
        counts = db.one("SELECT COUNT(*) AS n FROM trials WHERE session_id=? AND status IN ('submitted','skipped')", (session['id'],))
        result = dict(participant_code=session['display_code'], condition=session['condition'],
                      attempt_no=session['attempt_no'], sequence_no=session['sequence_no'],
                      first_condition=session['first_condition'], status=session['status'],
                      total=session['task_count'], completed_count=counts['n'],
                      attention_failures=session['attention_failures'], local_practice=not store.postgres,
                      current=None)
        if session['status'] == 'active':
            row = current_trial(db, session)
            if row:
                item = items[row['item_id']]
                # The timer is set when the browser acknowledges image loading.
                if not row['viewed_at']:
                    row['viewed_at'] = now()
                    db.execute('UPDATE trials SET viewed_at=? WHERE id=?', (row['viewed_at'], row['id']))
                trial = dict(id=row['id'], position=row['position'], brand=BRANDS[item['brand']],
                             status=row['status'], image_url=f"/api/trials/{row['id']}/image",
                             image_ready=bool(row['image_ready_at']),
                             initial_label=row['initial_label'], initial_confidence=row['initial_confidence'])
                if row['status'] == 'review' and session['condition'] == 'ai':
                    trial['ai'] = dict(prediction=row['shown_prediction'], confidence=row['shown_confidence'],
                                       gradcam_url=f"/api/trials/{row['id']}/gradcam",
                                       assets_ready=bool(row['ai_assets_ready_at']))
                result['current'] = trial
        return result

    @app.get('/')
    def home():
        return render_template('home.html', local=not store.postgres, n=task_count)

    @app.get('/without-ai')
    @app.get('/with-ai')
    def study():
        condition = 'ai' if request.path == '/with-ai' else 'baseline'
        return render_template('study.html', condition=condition, local=not store.postgres, n=task_count)

    @app.get('/healthz')
    def health():
        with store.connect() as db:
            db.one('SELECT id FROM sessions LIMIT 1')
        return jsonify(status='ok', storage='supabase' if store.postgres else 'local-practice', study_items=len(items))

    @app.post('/api/start')
    def start():
        data = request.get_json()
        code = re.sub(r'\s+', ' ', text_value(data.get('participant_code'), 60, 'Participant code'))
        if not re.fullmatch(r'[\w .@+-]{2,60}', code):
            abort(400, description='Use a participant code of 2–60 letters, numbers, spaces, or . @ + - _.')
        condition = data.get('condition')
        if condition not in ('baseline', 'ai'):
            abort(400, description='Unknown study condition.')
        if data.get('consent') is not True:
            abort(400, description='Please confirm your consent to continue.')
        try:
            request_id = str(uuid.UUID(data.get('request_id', '')))
        except (ValueError, TypeError, AttributeError):
            abort(400, description='A valid start request ID is required.')
        familiarity = data.get('familiarity')
        if familiarity is not None:
            integer(familiarity, 1, 5, 'Familiarity')
        canonical = code.casefold()
        with store.connect() as db:
            db.lock_participant(canonical)
            existing = db.one('SELECT * FROM sessions WHERE request_id=?', (request_id,))
            if existing:
                if existing['participant_code'] != canonical or existing['condition'] != condition:
                    abort(409, description='This start request was already used. Please reload.')
                return jsonify(session_token=existing['id'], state=state(db, existing))
            previous = db.all('SELECT * FROM sessions WHERE participant_code=? ORDER BY sequence_no', (canonical,))
            attempt = 1 + sum(s['condition'] == condition for s in previous)
            sequence = len(previous) + 1
            first = previous[0]['first_condition'] if previous else condition
            seen_rows = db.all('SELECT t.item_id, COUNT(*) AS n FROM trials t JOIN sessions s ON s.id=t.session_id WHERE s.participant_code=? GROUP BY t.item_id', (canonical,))
            seen = {r['item_id']: r['n'] for r in seen_rows}
            rng = secrets.SystemRandom()
            unseen = [key for key in items if key not in seen]
            selected = rng.sample(unseen, min(task_count, len(unseen)))
            if len(selected) < task_count:
                selected += rng.sample([key for key in items if key not in selected], task_count-len(selected))
            rng.shuffle(selected)
            session_id = str(uuid.uuid4())
            db.execute('''INSERT INTO sessions
                (id,request_id,participant_code,display_code,condition,attempt_no,sequence_no,first_condition,status,
                 task_count,dataset_version,familiarity,consent_at,completion_code)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (session_id, request_id, canonical, code, condition, attempt, sequence, first, 'attention',
                 task_count, manifest['version'], familiarity, now(), 'PI-'+secrets.token_hex(5).upper()))
            for position, key in enumerate(selected, 1):
                db.execute('INSERT INTO trials (id,session_id,position,item_id,prior_exposures) VALUES (?,?,?,?,?)',
                           (str(uuid.uuid4()), session_id, position, key, seen.get(key, 0)))
            session = db.one('SELECT * FROM sessions WHERE id=?', (session_id,))
            return jsonify(session_token=session_id, state=state(db, session))

    @app.get('/api/state')
    def get_state():
        with store.connect() as db:
            session = auth_session(db)
            return jsonify(state(db, session))

    @app.post('/api/attention')
    def attention():
        answer = text_value(request.get_json().get('answer'), 40, 'Answer')
        with store.connect() as db:
            session = auth_session(db)
            if session['status'] != 'attention':
                return jsonify(state(db, session))
            passed = answer == 'image_evidence'
            db.execute('INSERT INTO attention_events (id,session_id,answer,passed,created_at) VALUES (?,?,?,?,?)',
                       (str(uuid.uuid4()), session['id'], answer, int(passed), now()))
            if passed:
                db.execute("UPDATE sessions SET status='active', attention_passed_at=? WHERE id=?", (now(), session['id']))
                session['status'] = 'active'
            else:
                db.execute('UPDATE sessions SET attention_failures=attention_failures+1 WHERE id=?', (session['id'],))
                session['attention_failures'] += 1
            return jsonify(state(db, session))

    @app.get('/api/trials/<trial_id>/<kind>')
    def image_asset(trial_id, kind):
        if kind not in ('image', 'gradcam'):
            abort(404)
        with store.connect() as db:
            session = auth_session(db)
            row = requested_trial(db, session, trial_id)
            require_current(db, session, row)
            item = items[row['item_id']]
            if kind == 'gradcam' and (session['condition'] != 'ai' or row['status'] != 'review'):
                abort(403, description='AI assistance becomes available after your independent answer.')
            asset = item['original'] if kind == 'image' else row['shown_gradcam']
        return send_file(BASE / 'data/stimuli' / asset, download_name='product-image' + Path(asset).suffix)

    @app.post('/api/trials/<trial_id>/ready')
    def image_ready(trial_id):
        phase = request.get_json().get('phase')
        if phase not in ('original', 'ai'):
            abort(400, description='Unknown image phase.')
        with store.connect() as db:
            session = auth_session(db)
            row = requested_trial(db, session, trial_id)
            require_current(db, session, row)
            if phase == 'ai':
                if session['condition'] != 'ai' or row['status'] != 'review':
                    abort(409, description='AI assistance is not available yet.')
                db.execute('UPDATE trials SET ai_assets_ready_at=COALESCE(ai_assets_ready_at,?) WHERE id=?', (now(), trial_id))
            else:
                db.execute('UPDATE trials SET image_ready_at=COALESCE(image_ready_at,?) WHERE id=?', (now(), trial_id))
            return jsonify(ok=True)

    @app.post('/api/trials/<trial_id>/initial')
    def initial(trial_id):
        data = request.get_json()
        answer = label(data.get('label'))
        confidence = integer(data.get('confidence'), 1, 5, 'Confidence')
        with store.connect() as db:
            session = auth_session(db)
            row = requested_trial(db, session, trial_id)
            if session['condition'] == 'baseline':
                comment = text_value(data.get('comment', ''), 2000, 'Comment')
                uncertain = data.get('uncertain', False)
                if type(uncertain) is not bool:
                    abort(400, description='Invalid uncertainty flag.')
                if data.get('reasons', []) != [] or data.get('trust') is not None:
                    abort(400, description='AI trust and reasons are not part of this condition.')
                if row['status'] == 'submitted':
                    return jsonify(state(db, session))
                require_current(db, session, row)
                if not row['image_ready_at']:
                    abort(409, description='Wait for the image to load, or report an image problem.')
                stamp = now()
                # Baseline has one submission. Keep both export columns for compatibility;
                # retain any independent answer already saved by an older practice client.
                db.execute('''UPDATE trials SET status='submitted',
                    initial_label=COALESCE(initial_label,?),initial_confidence=COALESCE(initial_confidence,?),
                    initial_submitted_at=COALESCE(initial_submitted_at,?),final_label=?,final_confidence=?,
                    uncertain=?,reasons=?,comment=?,submitted_at=? WHERE id=?''',
                    (answer,confidence,stamp,answer,confidence,int(uncertain),'[]',comment,stamp,trial_id))
                finish_if_needed(db, session)
                return jsonify(state(db, session))
            if row['status'] in ('review','submitted'):
                if row['initial_label'] != answer or row['initial_confidence'] != confidence:
                    abort(409, description='Your independent answer is already saved.')
                return jsonify(state(db, session))
            require_current(db, session, row)
            if not row['image_ready_at']:
                abort(409, description='Wait for the image to load, or report an image problem.')
            stamp = now()
            item = items[row['item_id']]
            assisted = session['condition'] == 'ai'
            db.execute('''UPDATE trials SET status='review',initial_label=?,initial_confidence=?,initial_submitted_at=?,
                ai_revealed_at=?,shown_prediction=?,shown_confidence=?,shown_gradcam=? WHERE id=?''',
                (answer, confidence, stamp, stamp if assisted else None,
                 item['ai_prediction'] if assisted else None, item['ai_confidence'] if assisted else None,
                 item['gradcam'] if assisted else None, trial_id))
            return jsonify(state(db, session))

    @app.post('/api/trials/<trial_id>/final')
    def final(trial_id):
        data = request.get_json()
        answer = label(data.get('label'))
        confidence = integer(data.get('confidence'), 1, 5, 'Confidence')
        comment = text_value(data.get('comment', ''), 2000, 'Comment')
        uncertain = data.get('uncertain', False)
        if type(uncertain) is not bool:
            abort(400, description='Invalid uncertainty flag.')
        reasons = data.get('reasons', [])
        if not isinstance(reasons, list) or len(reasons)>len(REASONS) or any(not isinstance(x, str) or x not in REASONS for x in reasons):
            abort(400, description='Invalid feedback reason.')
        with store.connect() as db:
            session = auth_session(db)
            row = requested_trial(db, session, trial_id)
            if row['status'] == 'submitted':
                # A retried submission never creates or overwrites a response.
                return jsonify(state(db, session))
            require_current(db, session, row)
            if row['status'] != 'review':
                abort(409, description='Save your independent answer first.')
            trust = None
            if session['condition'] == 'ai':
                trust = integer(data.get('trust'), 1, 5, 'Trust')
                if not reasons:
                    abort(400, description='Select at least one reason for your trust or decision.')
                if 'unchanged_answer' in reasons and answer != row['initial_label']:
                    abort(400, description='Select the unchanged-answer option only when keeping your independent answer.')
                if not row['ai_assets_ready_at']:
                    abort(409, description='Wait for the AI heatmap to load, or report an image problem.')
            elif reasons:
                abort(400, description='AI reasons are not part of this condition.')
            db.execute('''UPDATE trials SET status='submitted',final_label=?,final_confidence=?,uncertain=?,trust=?,
                reasons=?,comment=?,submitted_at=? WHERE id=?''',
                (answer,confidence,int(uncertain),trust,json.dumps(sorted(set(reasons))),comment,now(),trial_id))
            finish_if_needed(db, session)
            return jsonify(state(db, session))

    @app.post('/api/trials/<trial_id>/skip')
    def skip(trial_id):
        reason = request.get_json().get('reason')
        if reason not in ('image_load_error', 'heatmap_load_error'):
            abort(400, description='A technical image problem is required to skip.')
        with store.connect() as db:
            session = auth_session(db)
            row = requested_trial(db, session, trial_id)
            if row['status'] == 'skipped':
                return jsonify(state(db, session))
            require_current(db, session, row)
            if reason == 'heatmap_load_error' and (session['condition'] != 'ai' or row['status'] != 'review'):
                abort(400, description='No heatmap is expected in this phase.')
            db.execute("UPDATE trials SET status='skipped',skip_reason=?,submitted_at=? WHERE id=?", (reason,now(),trial_id))
            finish_if_needed(db, session)
            return jsonify(state(db, session))

    @app.post('/api/survey')
    def survey():
        data = request.get_json()
        workload = integer(data.get('workload'), 1, 7, 'Mental effort')
        feedback = text_value(data.get('feedback', ''), 4000, 'Feedback')
        with store.connect() as db:
            session = auth_session(db)
            if session['status'] == 'completed':
                return jsonify(state(db, session))
            if session['status'] != 'survey':
                abort(409, description='Complete your trials before the final questions.')
            usefulness = integer(data.get('usefulness'), 1, 7, 'AI usefulness') if session['condition'] == 'ai' else None
            stamp = now()
            db.execute("UPDATE sessions SET status='completed',workload=?,usefulness=?,feedback=?,survey_submitted_at=?,completed_at=? WHERE id=?",
                       (workload,usefulness,feedback,stamp,stamp,session['id']))
            session.update(status='completed', completion_code=session['completion_code'])
            return jsonify(state(db, session))

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            password = app.config['ADMIN_PASSWORD']
            if not password:
                abort(503, description='Researcher access is disabled until ADMIN_PASSWORD is configured.')
            auth = request.authorization
            if not auth or not secrets.compare_digest(auth.username or '', 'admin') or not secrets.compare_digest(auth.password or '', password):
                return Response('Researcher sign-in required.', 401, {'WWW-Authenticate': 'Basic realm="Product Inspector Researcher"'})
            return view(*args, **kwargs)
        return wrapped

    def all_records(db):
        return db.all('SELECT * FROM sessions ORDER BY consent_at'), db.all('SELECT * FROM trials ORDER BY session_id,position')

    @app.get('/admin')
    @admin_required
    def admin():
        with store.connect() as db:
            sessions, trials = all_records(db)
        summary = []
        for condition in ('baseline','ai'):
            completed = [s for s in sessions if s['condition']==condition and s['status']=='completed']
            summary.append(dict(condition=condition, runs=len(completed), participants=len({s['participant_code'] for s in completed})))
        return render_template('admin.html', sessions=list(reversed(sessions)), summary=summary,
                               response_count=sum(t['status']=='submitted' for t in trials), local=not store.postgres)

    def csv_response(rows, filename, fields=None):
        fields = fields or (list(rows[0]) if rows else ['no_records'])
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            # Protect spreadsheet users from formula injection in free text.
            writer.writerow({k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.get('/admin/export/<kind>.csv')
    @admin_required
    def export(kind):
        with store.connect() as db:
            sessions, trials = all_records(db)
            events = db.all('SELECT * FROM attention_events ORDER BY created_at') if kind=='attention' else []
        if kind not in ('sessions','trials','attention'):
            abort(404)
        # Session tokens/request IDs are authentication credentials: never export them.
        # Retain the existing internal export key; participants do not see a code.
        run_ids = {s['id']: s['completion_code'] for s in sessions}
        by_session = {s['id']: s for s in sessions}
        completed_rank = {}
        rank = {}
        for s in sorted(sessions, key=lambda s: (s['completed_at'] or '9999',s['sequence_no'])):
            if s['status']=='completed':
                key=(s['participant_code'],s['condition'])
                rank[key]=rank.get(key,0)+1
                completed_rank[s['id']]=rank[key]
        rows = []
        for s in sessions:
            if kind == 'sessions':
                row={k:v for k,v in s.items() if k not in ('id','request_id','completion_code')}
                row.update(run_id=run_ids[s['id']],completed_rank=completed_rank.get(s['id'],''),
                           duration_seconds=elapsed(s['consent_at'],s['completed_at']),
                           storage_mode='supabase' if store.postgres else 'local-practice')
                rows.append(row)
        if kind == 'trials':
            for t in trials:
                s=by_session[t['session_id']];item=items[t['item_id']]
                row={k:v for k,v in t.items() if k not in ('id','session_id')}
                row.update(run_id=run_ids[t['session_id']],participant_code=s['participant_code'],condition=s['condition'],
                           attempt_no=s['attempt_no'],sequence_no=s['sequence_no'],first_condition=s['first_condition'],
                           session_status=s['status'],completed_rank=completed_rank.get(s['id'],''),
                           dataset_version=s['dataset_version'],study_index=item['study_index'],brand=item['brand'],
                           ground_truth=item['ground_truth'],ai_prediction=item['ai_prediction'],
                           ai_confidence=item['ai_confidence'],calibrated_fake_probability=item['calibrated_fake_probability'],
                           initial_correct=int(t['initial_label']==item['ground_truth']) if t['initial_label'] else '',
                           final_correct=int(t['final_label']==item['ground_truth']) if t['final_label'] else '',
                           changed_answer=int(t['initial_label']!=t['final_label']) if t['final_label'] else '',
                           initial_ai_agreement=int(t['initial_label']==item['ai_prediction']) if t['initial_label'] else '',
                           final_ai_agreement=int(t['final_label']==item['ai_prediction']) if t['final_label'] else '',
                           initial_seconds=elapsed(t['image_ready_at'],t['initial_submitted_at']),
                           review_seconds=elapsed(t['initial_submitted_at'],t['submitted_at'])
                               if s['condition']=='ai' or t['initial_submitted_at']!=t['submitted_at'] else '',
                           total_seconds=elapsed(t['image_ready_at'],t['submitted_at']))
                rows.append(row)
        if kind=='attention':
            rows=[dict(run_id=run_ids[e['session_id']],answer=e['answer'],passed=e['passed'],created_at=e['created_at']) for e in events]
        return csv_response(rows, f'a3_{kind}.csv')
    return app

if __name__ == '__main__':
    application=create_app()
    application.run(host='127.0.0.1', port=int(os.getenv('PORT','5001')), debug=False)
