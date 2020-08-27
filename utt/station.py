from datetime import datetime, timezone

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.gct import as_gct
from utt.model import db, \
    Station, \
    System

@app.route('/station')
def list_stations():
    stations = Station.query.join('system').order_by(System.rank.asc(), Station.name.asc())
    return render_template('station/overview.html', stations=stations.all())
