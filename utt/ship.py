from datetime import datetime, timezone

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.model import db, \
    autovivify, \
    get_station, \
    Token, \
    Ship, \
    ShipClass, \
    ShipSighting 

def now():
    return datetime.now(timezone.utc)

@app.route('/v1/ship/add', methods=['POST'])
def ship_add():
    payload = request.get_json(force=True)
    token = Token.verify(payload['token'])
    station = get_station(payload['system'], payload['station'])
    count = 0
    for ship_sighting in payload['ships']:
        ship_class = autovivify(ShipClass, {'name': ship_sighting['class']})
        ship = autovivify(Ship, {
            'registration': ship_sighting['registration'],
            'ship_class': ship_class,
            'name': ship_sighting['name'],
            'captain': ship_sighting['captain'],
        })
        db.session.add(ShipSighting(
            ship=ship,
            station=station,
            token=token,
        ))
        count += 1
    db.session.commit()
    print('Recorded {} ship positions on {} by {}'.format(count, station.name, token.character.name))
    return jsonify({'success': True, 'num_recorded': count})

@app.route('/ship/')
def ship_overview():
    ships = Ship.query.order_by(Ship.name.asc())

    return render_template('ship/overview.html', ships=ships)
