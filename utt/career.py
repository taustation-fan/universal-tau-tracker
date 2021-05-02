from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json

from flask import request, jsonify, Response, render_template
from sqlalchemy import func

from .app import app
from utt.util import today_datetime

from utt.model import db, \
                      get_station, \
                      System, \
                      Station, \
                      Character, \
                      Token, \
                      CareerBatchSubmission, \
                      CareerTask, \
                      CareerTaskReading, \
                      InvalidTokenException

def now():
    return datetime.now(timezone.utc)

@app.route('/v1/career-task/add', methods=['POST'])
def career_task_add():
    payload = request.get_json(force=True)
    mandatory = set(('token', 'station', 'system', 'career', 'rank', 'tasks'))
    missing_attrs = [a for a in mandatory if not payload.get(a)]
    if missing_attrs:
        message = 'Missing attributes: '  + ', '.join(missing_attrs)
        return jsonify({'recorded': False, 'missing': missing_attrs, message: message})

    station_name = payload['station']
    try:
        token = Token.verify(payload['token'])
        token.record_script_version(payload.get('script_version'))
    except InvalidTokenException:
        return jsonify({'recorded': False, 'message': 'Invalid token'})

    if token is None:
        return jsonify({'recorded': False, 'message': 'Invalid token'})
    if 'Confined to the' in station_name or 'Doing activity' in station_name:
        return jsonify({'recorded': False, 'message': '{} does not look like a valid station name'.format(station_name)})
    station = get_station(payload['system'], station_name)
    
    batch = CareerBatchSubmission(
        token=token,
        character=token.character,
        station=station,
        career=payload['career'],
        rank=payload['rank'],
    )
    db.session.add(batch)

    response = {'character': token.character.name}

    factors = []

    for task, bonus in payload['tasks'].items():
        bonus = float(bonus)
        career_task = CareerTask.query.filter_by(name=task).first()
        if career_task is None:
            career_task = CareerTask(
                name=task,
                career=payload['career'],
                bonus_baseline=bonus,
            )
            db.session.add(career_task)
        elif career_task.bonus_baseline is None or career_task.bonus_baseline > bonus:
            career_task.bonus_baseline = bonus
            
        tr = CareerTaskReading(
            batch_submission=batch,
            career_task=career_task,
            bonus=bonus,
        )
        db.session.add(tr)
        factors.append(tr.factor)
    factor = max(factors);
    batch.factor = factor
    if factor:
        print('Recorded factor {} for station {}, {}'.format(factor, station.name, datetime.now()))

    response['recorded'] = True
    response['factor'] = factor

    # find factors for other stations in the system
    date_limit = today_datetime()
    stations = Station.query.filter_by(system_id=station.system_id)
    system_factors = {}

    cbs = CareerBatchSubmission
    for st in stations.all():
        if st.name == station_name:
            continue
        qry = cbs.query.filter(cbs.when > date_limit).filter_by(station_id=st.id).order_by(cbs.when.desc())
        bs = qry.first()
        if bs:
            factor = max(o.factor for o in bs.readings)
            system_factors[st.name] = factor
    if system_factors:
        response['system_factors'] = system_factors
  
    db.session.commit()

    return jsonify(response)

@app.route('/v1/career-task/summary')
def summary():
    token_str = request.args.get('token')
    assert token_str, 'Missing token'
    token = Token.query.filter_by(token=token_str).first()
    assert token, 'Invalid token'
    assert token.full_read_permission, 'Permission denied'

    stations = Station.query.all()

    factors = defaultdict(dict) # factors = {'YC Ceti': {'Cape Verde Stronghold': 1.25}}

    for station in stations:
        bs = CareerBatchSubmission.query.filter_by(station_id=station.id).filter(CareerBatchSubmission.factor != None).order_by(CareerBatchSubmission.when.desc()).first()
        if not bs:
            continue
        if (now() - bs.when).total_seconds() > 6 * 3600:
            continue
        factors[station.system.name][station.name] = bs.factor

    result = ''
    for system in sorted(factors.keys()):
        for station in sorted(factors[system].keys()):
            factor = factors[system][station]
            result += '{:.2f}  {:20} {:30}\n'.format(factor, system, station)

    return Response(result, mimetype='text/plain')
            

@app.route('/v1/career-task/stats-by-character')
def career_stats_by_player():
    results = db.session.query(Character.name, func.count(CareerBatchSubmission.id)) \
              .join(Character).group_by(Character.name).all()
    by_player = {}
    for r in results:
        by_player[r[0]] = r[1]
    return jsonify({'data': by_player})

@app.route('/v1/career-task/station-needs-update/<system>/<station>')
def career_station_needs_update(system, station):
    try:
        st = get_station(system, station, create=False)
    except AssertionError:
        return jsonify({'needs_update': True})

    return jsonify({'needs_update': station.needs_career_update})

@app.route('/career')
def career_overview():
    systems = System.query.order_by(System.name).all()

    return render_template('career_overview.html', systems=systems)

@app.route('/career/system/<id>')
def system_career_graph(id):
    system = System.query.filter_by(id=id).one()
    stations = system.stations
    limit = today_datetime()
    datasets = []
    CBS = CareerBatchSubmission
    # colors from https://htmlcolorcodes.com/color-chart/
    colors = '#cd6155 #9b59b6 #2980b9 #1abc9c #16a085 #f1c40f #f39c12 #7f8c8d #f1948a #85c1e9'.split(' ')
    for idx, station in enumerate(stations):
        data = []
        q = CBS.query.filter(CBS.station_id == station.id, CBS.when <= limit).order_by(CBS.when)
        for batch in q:
            if batch.factor:
                data.append({'x': batch.when.strftime( "%Y-%m-%dT%H:%M:%SZ"), 'y': batch.factor})
        if data:
            datasets.append({
                'label': station.name,
                'data': data,
                'backgroundColor': colors[idx],
            })
    ctx = {
        'system': system,
        'datasets': json.dumps(datasets),
        'systems': System.query.all()
    }
    return render_template('system_career_factor.html', **ctx)
