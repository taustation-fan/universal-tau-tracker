from datetime import datetime, timedelta, timezone
import json

from flask import request, jsonify, Response, render_template
from sqlalchemy import func

from .app import app

from utt.model import db, \
                      get_station, \
                      Token, \
                      FuelPriceReading

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

    token = Token.query.filter_by(token=token_str).first()
    if token is None:
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

    response = {'recorded': True, 'systems': { station.system.name: { station.name: price_per_g } } }
    print('Recorded fuel price {} for station {} by  {}, {}'.format(price_per_g, station.name, token.character.name, datetime.now()))
    db.session.commit()

    return jsonify(response)
