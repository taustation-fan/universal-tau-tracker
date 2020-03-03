from datetime import datetime, timedelta, timezone
import json
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
from flask import request, jsonify, Response, render_template, send_file
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
        'message': render_fuel_add_response(station, token_str),
    }
    print('Recorded fuel price {} for station {} by  {}, {}'.format(price_per_g, station.name, token.character.name, datetime.now()))

    db.session.commit()

    return jsonify(response)

def render_fuel_add_response(current_station, token):
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
            'token': token,
        })
    return str(render_template('fuel_short_table.html', rows=rows))

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

@app.route('/fuel/lowest/<token>')
def fuel_lowest(token):
    token = Token.query.filter_by(token=token).first()
    assert token, 'Need valid token'
    n = now()
    
    refuel = FPS.query.order_by(FPS.last_price.asc()).limit(15)
    rows = [{
                'station_short_name': r.station_short_name,
                'last_price': r.last_price,
                'age_gct':  gct_duration(n - r.last_reading),
             } for r in refuel]

    
    return render_template('fuel_refuel.html', rows=rows)
