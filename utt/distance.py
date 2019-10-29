import pytz
import json
import re
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
import numpy as np


from flask import request, jsonify, Response, url_for, render_template, send_file
from sqlalchemy import func

from .app import app

from utt.gct import as_gct, parse_gct
from utt.model import db, \
                      get_station, \
                      get_station_pair, \
                      System, \
                      Station, \
                      Character, \
                      Token, \
                      StationPair, \
                      StationDistanceReading

@app.route('/v1/distance/add', methods=['POST'])
def add_distance():
    payload = request.get_json(force=True)
    mandatory = set(('token', 'source', 'system', 'schedules'))
    missing_attrs = [a for a in mandatory if not payload.get(a)]
    if missing_attrs:
        message = 'Missing attributes: '  + ', '.join(missing_attrs)
        return jsonify({'recorded': False, 'missing': missing_attrs, message: message})

    token_str = payload['token']
    token = Token.query.filter_by(token=token_str).first()
    if token is None:
        return jsonify({'recorded': False, 'message': 'Invalid token'})

    station = get_station(payload['system'], payload['source'])
    count = 0
    new = 0
    for schedule in payload['schedules']:
        distances = [t for t in schedule['distances'] if t[0] and t[1]]
        if not distances:
            continue
        destination = get_station(payload['system'], schedule['destination'])
        pair = get_station_pair(station, destination)
        for d_tuple  in distances:
            try:
                departure, distance, travel_time = d_tuple
            except ValueError:
                departure, distance = d_tuple
                travel_time = None
            if not isinstance(distance, (int, float)):
                continue
            distance = int(distance)
            departure = parse_gct(departure) or departure
            count += 1
            existing = StationDistanceReading.query.filter_by(
                station_pair_id=pair.id,
                distance_km=distance,
                when=departure,
            ).first()
            if not existing:
                new += 1
                if travel_time and re.search('[0-9]', travel_time):
                    travel_time = int(re.sub(r'[^0-9]', '', travel_time))
                else:
                    travel_time = None
                sdr = StationDistanceReading(
                    station_pair=pair,
                    distance_km=distance,
                    when=departure,
                    travel_time_u=travel_time,
                    token=token,
                )
                db.session.add(sdr)
    db.session.commit()
    print('Recorded {} distance pairs ({} new) for {} by {}'.format(count, new, payload['source'], token.character.name))
    return jsonify({'recorded': True, 'message': 'Recorded {} distance pairs, of which {} were new. +1 brownie point'.format(count, new)})

@app.route('/distance')
def distance_overview():
    station_pairs = defaultdict(dict)

    total_count = 0;
    systems = []
    for system in System.query.order_by(System.rank, System.name):
        system_dict = {
            'id': system.id,
            'name': system.name,
            'station_pairs': {},
        }
        for sp in StationPair.query.filter_by(system_id=system.id):
            count = sp.readings_count
            if count > 0:
                total_count += count
                system_dict['station_pairs'][str(sp)] = {
                    'id': sp.id,
                    'count': count,
                    'url': url_for('distance_pair', id=sp.id),
                    'has_fit': sp.has_full_fit,
                    'fit_period_u': sp.fit_period_u,
                    'fit_min_distance_km': sp.fit_min_distance_km,
                    'fit_max_distance_km': sp.fit_max_distance_km,
                    'fit_phase': sp.fit_phase,
                }
        if system_dict['station_pairs']:
            systems.append(system_dict)
    if request.content_type == 'application/json':
        return jsonify(station_pairs)
    return render_template('distance_overview.html', systems=systems, total=total_count)

@app.route('/distance/pair/<id>')
def distance_pair(id):
    id = int(id)
    readings = []
    sdr_m = StationDistanceReading
    pair = StationPair.query.filter_by(id=id).one()
    for r in sdr_m.query.filter_by(station_pair_id=id).order_by(StationDistanceReading.when).all():
        readings.append({'x': r.when.astimezone(pytz.UTC).strftime( "%Y-%m-%dT%H:%M:%SZ"), 'y': r.distance_km})

    min_distance, max_distance = None, None
    if r:
        min_distance, max_distance = db.session.query(func.min(sdr_m.distance_km),
                                                      func.max(sdr_m.distance_km)) \
                                        .filter(sdr_m.station_pair_id == id).first()

    result = {
        'id': id,
        'station_a_name': pair.station_a.name,
        'station_b_name': pair.station_b.name,
        'system_name': pair.system.name,
        'pair_string': str(pair),
        'readings': readings,
        'min_distance': min_distance,
        'max_distance': max_distance,
        'has_prediction': pair.has_full_fit,
    }
    if request.content_type == 'application/json':
        return jsonify(result)
    result['readings'] = json.dumps(result['readings'])
    return render_template('distance_pair.html', **result)

@app.route('/distance/pair/<id>.csv')
def distance_pair_csv(id):
    id = int(id)
    pair = StationPair.query.filter_by(id=id).one()
    rows = ["Time/UTC,Time/GCT,Distance/km\n"]
    for r in StationDistanceReading.query.filter_by(station_pair_id=id).order_by(StationDistanceReading.when).all():
        when = r.when.astimezone(pytz.UTC)
        rows.append('{},{},{}\n'.format(
            when.strftime( "%Y-%m-%dT%H:%M:%SZ"),
            as_gct(when),
            r.distance_km,
        ))
    response = Response(''.join(rows), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=pair-{}.csv'.format(id)
    return response


@app.route('/distance/pair/<id>/prediction_png')
def distance_pair_prediction_png(id):
    pair_id = int(id)
    pair = StationPair.query.filter_by(id=pair_id).one()
    assert pair.fit_period_u is not None, 'No period fit known'
    assert pair.fit_min_distance_km is not None, 'No min distance fit known'
    assert pair.fit_max_distance_km is not None, 'No max distance fit known'
    assert pair.fit_phase is not None, 'No phase fit known'

    start = datetime.now(timezone.utc)
    end  = start + timedelta(days=1)
    SDR = StationDistanceReading
    readings = SDR.query.filter_by(station_pair_id=pair.id)\
               .filter(SDR.when >=start, SDR.when < end).order_by(SDR.when)
    x = []
    y = []
    for reading in readings:
        x.append(float(as_gct(reading.when, format=False)))
        y.append(float(reading.distance_km))

    xr = np.linspace(float(as_gct(start, format=False)), float(as_gct(end, format=False)), 1000)

    maxs = pair.fit_max_distance_km ** 2
    mins = pair.fit_min_distance_km ** 2

    baseline =(maxs + mins) / 2
    amplitude = (maxs - mins) / 2
    yr = np.sqrt(baseline +  amplitude * np.cos(xr * (2 * np.pi / pair.fit_period_u) + pair.fit_phase))

    plt.clf()
    plt.cla()
    plt.plot(xr, yr, 'b-', label='predicted values')

    if len(x) > 2:
        plt.plot(x, y, 'ro', label='Measurement')
    # plt.gcf().set_size_inches(12, 9)
    plt.title(str(pair))
    plt.ylabel('Distance/km')
    plt.xlabel('Time/u')
    plt.legend()
    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

class StationPosition:
    def __init__(self, station, time, phase):
        self.station = station
        self.time    = time
        self.phase   = phase

    @property
    def x(self):
        return self.station.fit_radius_km * math.cos(self.phase)

    @property
    def y(self):
        return self.station.fit_radius_km * math.sin(self.phase)

    def distance_to(self, other):
        return np.sqrt( (other.y - self.y) ** 2 + (other.x - self.x) ** 2)

def get_positions(system, time):
    stations = Station.query.filter_by(system_id=system.id).order_by(Station.fit_radius_km.desc()).all()
    base = stations.pop(0)

    initial_phase = 0
    if base.fit_period_u is not None:
        arg = time / base.fit_period_u
        arg - int(arg)
        initial_phase = 2 * np.pi * arg

    positions = [StationPosition(base, time, initial_phase)]
    for station in stations:
        pair = get_station_pair(station, base)
        arg = time / pair.fit_period_u
        arg -= int(arg)
        phase = pair.fit_phase + 2 * np.pi * arg
        positions.append(StationPosition(station, time, phase + initial_phase))
    return positions

@app.route('/distance/system/<system_id>.png')
def distance_system_png(system_id):
    system = System.query.filter_by(id=system_id).one()
    time = request.args.get('u')
    if time is None:
        time = float(as_gct(datetime.now(timezone.utc), format=False))
    else:
        time = float(time)

    positions = get_positions(system, time)

    x = [0] + [p.x for p in positions]
    y = [0] + [p.y for p in positions]

    size = positions[0].station.fit_radius_km * 1.1

    plt.clf()
    plt.cla()
    fig, ax = plt.subplots()
    plt.title('{} system'.format(system.name))
    plt.xlabel('x / km')
    plt.ylabel('y / km')
    plt.ylim(-size, size)
    plt.xlim(-size, size)
    ax.scatter(x, y)
    ax.annotate('Central body', (0.0, 0.0))
    for p in positions:
        ax.annotate(p.station.name, (p.x, p.y))
    img = BytesIO()
    plt.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

@app.route('/distance/system/<system_id>')
def distance_system(system_id):
    system = System.query.filter_by(id=system_id).one()
    dt = datetime.now(timezone.utc)
    time = float(as_gct(dt, format=False))
    
    return render_template('distance_system.html',
                           system_name=system.name,
                           system_id=system.id,
                           u=time,
                           gct=as_gct(dt),
                           positions=get_positions(system, time),
                           )
