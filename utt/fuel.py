from datetime import datetime, timedelta, timezone
import json
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
from flask import request, jsonify, Response, render_template, send_file
from sqlalchemy import func

from .app import app
from utt.util import today_datetime, today
from sqlalchemy.orm.exc import NoResultFound

from utt.model import db, \
                      get_station, \
                      Token, \
                      FuelPriceEstimation, \
                      FuelPriceReading, \
                      FuelPriceStatistics as FPS, \
                      Station, \
                      System, \
                      InvalidTokenException
from utt.gct import gct_duration

def now():
    return datetime.now(timezone.utc)

@app.route('/v1/fuel/add', methods=['POST'])
def fuel_add():
    payload = request.get_json(force=True)
    mandatory = set(('token', 'station', 'system', 'fuel_g', 'price'))
    missing_attrs = [a for a in mandatory if not payload.get(a)]
    if missing_attrs:
        message = 'Missing attributes: '  + ', '.join(missing_attrs)
        return jsonify({'recorded': False, 'missing': missing_attrs, message: message})

    token_str = payload['token']
    station_name = payload['station']

    try:
        token = Token.verify(payload['token'])
        token.record_script_version(payload.get('script_version'))
    except InvalidTokenException:
        return jsonify({'recorded': False, 'message': 'Invalid token'})

    station = get_station(payload['system'], station_name)
    price_per_g = payload['price'] / payload['fuel_g']
    
    reading = FuelPriceReading(
        token=token,
        station=station,
        fuel_g = payload['fuel_g'],
        price = payload['price'],
        price_per_g = price_per_g,
        when = now(),
    )
    db.session.add(reading)

    response = {
        'recorded': True,
        'systems': { station.system.name: { station.name: price_per_g } },
        'message': render_fuel_add_response(station, token_str),
    }
    print('Recorded fuel price {} for station {} by  {}, {}'.format(price_per_g, station.name, token.character.name, datetime.now()))

    db.session.commit()

    return jsonify(response)

def render_fuel_add_response(current_station, token):
    start_dt = now()
    reference_date = today_datetime()
    rows = []

    seen = set()

    for stat in FPS.query.filter(FPS.last_reading >= reference_date).order_by(FPS.last_price, FPS.station_name):
        station_name = stat.station_short_name or stat.station_name
        seen.add(station_name)
        diff = start_dt - stat.last_reading
        rows.append({
            'station_name': station_name,
            'is_current':   stat.station_id == current_station.id,
            'price_per_g':  stat.last_price,
            'age': gct_duration(start_dt - stat.last_reading),
        })
    # add estimations
    estimations = [e for e in FuelPriceEstimation.all_today() if e.station.short not in seen]
    for e in estimations:
        rows.append({
            'station_name': e.station.short,
            'is_current': False,
            'price_per_g': e.price_per_g,
            'age': '(est.)',
        })
    rows.sort(key=lambda e: e['price_per_g'])
    
    return str(render_template('fuel_short_table.html', rows=rows, token=token))

@app.route('/fuel')
def fuel_list():
    stats = FPS.query.order_by(FPS.system_rank, FPS.system_name, FPS.station_level, FPS.station_name).all()
    return render_template('fuel_list.html', rows=stats)

@app.route('/fuel/min_max.png')
def fuel_min_max_png():
    x = []
    y1 = []
    y2 = []
    for fps in FPS.query.order_by(FPS.station_level):
        x.append(fps.station_level)
        y1.append(fps.min_price)
        y2.append(fps.max_price)

    plt.clf()
    plt.cla()
    plt.title('Fuel price over station level')
    if x:
        plt.axes(xticks=list(range(1, x[-1], 2)))
    plt.plot(x, y1, 'bo', label='Min')
    plt.plot(x, y2, 'ro', label='Max')
    plt.xlabel('Station level')
    plt.ylabel('Fuel price in credits / g')
    plt.legend()
    plt.tight_layout()
    
    img = BytesIO()
    plt.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

@app.route('/fuel/stats/<token>.json')
def fuel_stats_json(token):
    token = Token.query.filter_by(token=token).first()
    assert token, 'Need valid token'
    n = now()

    estimations = FuelPriceEstimation.today_as_dict()
    ref_dt = today_datetime()
    def make_output_dict(r):
        has_current_reading = r.last_reading >= ref_dt
        common = {
                'station_short_name': r.station_short_name,
                'estimation': estimations.get(r.station_short_name),
                'station_name': r.station_name,
                'system_name': r.system_name,
                'min_price': r.min_price,
                'max_price': r.max_price,
             }
        if has_current_reading:
            return dict(
                **common,
                last_price=r.last_price,
                last_reading=r.last_reading.isoformat(),
             )
        elif common['estimation'] is not None:
            return common
        else:
            return None

    rows = []
    for r in FPS.query.order_by(FPS.last_price.asc()):
        d = make_output_dict(r)
        if d is not None:
            rows.append(d)
    rows.sort(key=lambda r: r.get('last_price') or r.get('estimation'))
    return jsonify({'stations': rows})

@app.route('/fuel/lowest/<token>')
def fuel_lowest(token):
    token = Token.query.filter_by(token=token).first()
    assert token, 'Need valid token'
    compare = bool(request.args.get('cmp', False))
    n = now()
    limit = today_datetime()
    
    refuel = FPS.query.filter(FPS.last_reading > limit).order_by(FPS.last_price.asc())
    measured = {r.station_short_name: r.last_price for r in refuel}
    measured_ts = {r.station_short_name: r.last_reading for r in refuel}

    estimations = FuelPriceEstimation.today_as_dict()

    all_short_names = set(estimations.keys()) | set(measured.keys())

    rows = [{
                'station_short_name': short,
                'last_price': measured.get(short),
                'measured_timestamp': measured_ts.get(short),
                'estimated_price': estimations.get(short), 
             } for short in all_short_names]
    if compare:
        for row in rows:
            if row['last_price'] and row['estimated_price']:
                error =  1000 * abs(row['last_price'] - row['estimated_price']) / row['estimated_price']
                row['error'] = error
                if error < 5:
                    classification = 'good'
                elif error < 20:
                    classification = 'ok'
                else:
                    classification = 'bad'
                row['classification'] = classification
    rows.sort(key=lambda r: r['last_price'] or r['estimated_price'])

    return render_template('fuel_refuel.html', rows=rows, compare=compare)

@app.route('/fuel/system/<id>')
def system_fuel_price(id):
    system = System.query.filter_by(id=id).one()
    stations = system.stations
    limit = today_datetime()
    datasets = []
    colors = '#cd6155 #9b59b6 #2980b9 #1abc9c #16a085 #f1c40f #f39c12 #7f8c8d #f1948a #85c1e9'.split(' ')
    FPR = FuelPriceReading
    for idx, station in enumerate(stations):
        data = []
        q = FPR.query.filter(FPR.station_id == station.id, FPR.when < limit).order_by(FPR.when.asc())
        for reading in q.all():
            data.append({'x': reading.when.strftime( "%Y-%m-%dT%H:%M:%SZ"), 'y': reading.price_per_g})
        if data:
            datasets.append({
                'label': station.name,
                'data': data,
                'borderColor': colors[idx],
            })
    ctx = {
        'system': system,
        'datasets': json.dumps(datasets),
        'systems': System.query.all()
    }
    return render_template('system_fuel_price.html', **ctx)

@app.route('/fuel/estimation/export')
def export_fuel_estimation():
    token = Token.verify(request.args.get('token'))
    date_string = request.args.get('date')
    if date_string is None:
        from datetime import date
        day = date.today()
    else:
        day = datetime.strptime(date_string, '%Y-%m-%d').date()

    rs = FuelPriceEstimation.query.filter_by(day=day).order_by(FuelPriceEstimation.station_id)
    result = {
        'date': str(day),
        'stations': {
            e.station.short: {
                'name': e.station.name,
                'estimated_fuel_price_per_g': e.price_per_g,
            }
            for e in rs
        }
    }
    return jsonify(result)

@app.route('/v1/fuel_estimation/add', methods=['POST'])
def fuel_estimation_add():
    payload = request.get_json(force=True)
    token = Token.verify(payload['token'])
    stations = payload['stations']
    date = today()
    print('Recording fuel price estimations for {} from {}, token {}'.format(date, token.character.name, token.id))
    FuelPriceEstimation.query.filter_by(day=date).delete()
    for station_name, price in stations.items():
        try:
            station = Station.query.filter_by(name=station_name).one()
            est = FuelPriceEstimation(
                station=station,
                day=date,
                price_per_g=price,
            ) 
            db.session.add(est)
        except NoResultFound:
            print('  Found no station {}'.format(station_name))
            
    db.session.commit()
    return jsonify({'recorded': True})
