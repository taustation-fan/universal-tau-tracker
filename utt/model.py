from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()

def get_station(system_name, station_name, create=True):
    system = System.query.filter_by(name=system_name).first()
    if not system:
        assert create, 'No such system {}'.format(system_name)
        system = System(name=system_name)
        db.session.add(system)
    station = Station.query.filter(Station.system_id == system.id, Station.name_lower == station_name.lower()).first()
    if not station:
        assert create, 'No such station {} in {} system'.format(station_name, system_name)

        assert not ('Confined to the' in station_name or 'Doing activity' in station_name), \
            '{} does not look like a proper station name'.format(station_name)
        station = Station(system=system, name=station_name, name_lower=station_name.lower())
        db.session.add(station)
    return station

## General classes
class System(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.ForeignKey('system.id'), nullable=False)
    system = db.relationship('System')
    name = db.Column(db.String(200), unique=True, nullable=False)
    name_lower = db.Column(db.String(200), unique=True, nullable=False)

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    
class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(80), unique=True, nullable=False)
    infotext = db.Column(db.String(250))
    character_id = db.Column(db.ForeignKey('character.id'), nullable=False)
    character = db.relationship('Character', backref=db.backref('tokens', lazy=True))
    full_read_permission = db.Column(db.Boolean(), nullable=False, default=False)

## Career task bonus tracking
class CareerBatchSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    when = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')
    character_id = db.Column(db.ForeignKey('character.id'), nullable=False)
    character = db.relationship('Character')
    career = db.Column(db.String(140), nullable=False)
    rank = db.Column(db.String(140), nullable=False)
    station_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station = db.relationship('Station')
    factor = db.Column(db.Float())

class CareerTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    career = db.Column(db.String(250))
    bonus_baseline = db.Column(db.Float())

class CareerTaskReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_submission_id = db.Column(db.ForeignKey('career_batch_submission.id'), nullable=False)
    batch_submission = db.relationship('CareerBatchSubmission', backref=db.backref('readings', lazy=True))
    career_task_id = db.Column(db.ForeignKey('career_task.id'), nullable=False)
    career_task = db.relationship('CareerTask', backref='readings')
    bonus = db.Column(db.Float(), nullable=False)

    @property
    def factor(self):
        baseline = self.career_task.bonus_baseline
        if baseline is None:
            baseline = db.session.query(func.min(CareerTaskReading.bonus)).filter_by(career_task_id=self.career_task_id).first()
            if baseline is None:
                return None
            baseline = baseline[0]
            self.career_task.bonus_baseline = baseline
            db.session.add(self.career_task)

        return self.bonus / baseline

## Station distances
def get_station_pair(a, b):
    (station_a, station_b) = sorted((a, b), key=lambda x: x.name_lower)
    pair = StationPair.query.filter_by(station_a_id=station_a.id, station_b_id=station_b.id).first()
    if pair is None:
        pair = StationPair(
            station_a=station_a,
            station_b=station_b,
            system=a.system,
        )
        db.session.add(pair)
    return pair
            

class StationPair(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    system_id = db.Column(db.ForeignKey('system.id'), nullable=False)
    system = db.relationship('System')

    station_a_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station_a = db.relationship('Station', foreign_keys=[station_a_id])

    station_b_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station_b = db.relationship('Station', foreign_keys=[station_b_id])

    __table_args__ = (
        db.UniqueConstraint('station_a_id', 'station_b_id'),
    )    
    def __str__(self):
        return '{} ↔ {}'.format(self.station_a.name, self.station_b.name)


class StationDistanceReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    station_pair_id = db.Column(db.ForeignKey('station_pair.id'), nullable=False)
    station_pair = db.relationship('StationPair', backref='readings')

    distance_km = db.Column(db.Integer, nullable=False)
    when = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')
