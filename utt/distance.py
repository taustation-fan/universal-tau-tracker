import json
from collections import defaultdict
from datetime import datetime, timedelta

from flask import request, jsonify, Response
from sqlalchemy import func

from .app import app

from utt.gct import parse_utc
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
    for schedule in payload['schedules']:
        destination = get_station(payload['system'], schedule['destination'])
        pair = get_station_pair(station, destination)
        for (departure, distance) in schedule['distances']:
            departure = parse_utc(departure) or departure
            count += 1
            sdr = StationDistanceReading(
                station_pair=pair,
                distance_km=distance,
                when=departure,
                token=token,
            )
            db.session.add(sdr)
    db.session.commit()
    print('Recorded {} distance pairs for {} by {}'.format(count, payload['source'], token.character.name))
    return jsonify({'recorded': True, 'message': 'Success'})
