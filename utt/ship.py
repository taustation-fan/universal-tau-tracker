import json
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.gct import as_gct
from utt.model import (
    db,
    autovivify,
    get_station,
    Token,
    Ship,
    ShipClass,
    ShipSighting ,
    Station,
    System,
)

def now():
    return datetime.now(timezone.utc)

@app.route('/v1/ship/add', methods=['POST'])
def ship_add():
    payload = request.get_json(force=True)
    token = Token.verify(payload['token'])
    token.record_script_version(payload.get('script_version'))
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
        if not ship.captain and ship_sighting['captain']:
            ship.captain = ship_sighting['captain']
            db.session.add(ship)
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
    ships = Ship.query.order_by(Ship.captain.asc(), Ship.name.asc())

    return render_template('ship/overview.html', ships=ships)

def ship_timeline(ship):
    stations = Station.query.join(System).filter(Station.id.in_(
        db.session.query(ShipSighting.station_id).filter(ShipSighting.ship_id == ship.id)
    )).order_by(System.rank.asc(), Station.name.asc()).all()
    layers = {station.id: layer for layer, station in enumerate(stations)}

    sightings = ship.sightings
    timeline_start = sightings[0].when.date()
    timeline_end = sightings[-1].when.date() + timedelta(days=1)
    data = []
    for s in ship.sighting_streaks:
        data.append({
            'title': s.station.short or s.station.name,
            'start': s.first.when.isoformat(),
            'end':   s.last.when.isoformat(),
            'layer': layers[s.station.id],
        })
    layers_seen = {d['layer'] for d in data}
    return {
        'start': timeline_start,
        'end': timeline_end,
        'data': json.dumps(data),
    }

@app.route('/ship/<registration>')
def ship_detail(registration):
    ship = Ship.query.filter_by(registration=registration).one()

    return render_template('ship/detail.html', ship=ship, timeline=ship_timeline(ship))
