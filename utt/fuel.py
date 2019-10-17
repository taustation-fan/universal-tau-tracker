from datetime import datetime, timedelta, timezone
import json

from flask import request, jsonify, Response, render_template
from sqlalchemy import func

from .app import app

from utt.model import db, \
                      get_station, \
                      Token, \
                      FuelPriceReading, \
                      FuelPriceStatistics as FPS
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

    response = {
        'recorded': True,
        'systems': { station.system.name: { station.name: price_per_g } },
        'message': render_fuel_add_response(station),
    }
    print('Recorded fuel price {} for station {} by  {}, {}'.format(price_per_g, station.name, token.character.name, datetime.now()))

    db.session.commit()

    return jsonify(response)

def render_fuel_add_response(current_station):
    start_dt = now()
    reference_date = start_dt - timedelta(hours=8)
    rows = []

    for stat in FPS.query.filter(FPS.last_reading >= reference_date).order_by(FPS.last_price, FPS.station_name):
        station_name = stat.station_short_name or stat.station_name
        diff = start_dt - stat.last_reading
        rows.append({
            'station_name': station_name,
            'is_current':   stat.station_id == current_station.id,
            'price_per_g':  '{:.1f}'.format(stat.last_price),
            'age': gct_duration(start_dt - stat.last_reading),
        })
    return str(render_template('fuel_short_table.html', rows=rows))

@app.route('/fuel')
def fuel_list():
    stats = FPS.query.order_by(FPS.system_name, FPS.station_level, FPS.station_name).all()
    return render_template('fuel_list.html', rows=stats)
