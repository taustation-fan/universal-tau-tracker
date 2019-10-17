from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()

def get_station(system_name, station_name, create=True):
    system = System.query.filter(func.lower(System.name)==system_name.lower()).first()
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
    system = db.relationship('System', backref='stations')
    name = db.Column(db.String(200), unique=True, nullable=False)
    short = db.Column(db.String())
    name_lower = db.Column(db.String(200), unique=True, nullable=False)
    fit_radius_km = db.Column(db.Float)
    fit_period_u = db.Column(db.Float)

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

    # fitted parameters of this station pair
    fit_period_u = db.Column(db.Float)
    fit_min_distance_km = db.Column(db.Float)
    fit_max_distance_km = db.Column(db.Float)
    fit_phase = db.Column(db.Float)

    __table_args__ = (
        db.UniqueConstraint('station_a_id', 'station_b_id'),
    )    
    def __str__(self):
        return '{} ↔ {}'.format(self.station_a.name, self.station_b.name)

    @property
    def has_full_fit(self):
        return self.fit_period_u        is not None \
           and self.fit_min_distance_km is not None \
           and self.fit_max_distance_km is not None \
           and self.fit_phase           is not None

    @property
    def baseline_amptlitude_pair(self):
        if self.fit_max_distance_km is None or self.fit_min_distance_km is None:
            return None, None
        maxs = self.fit_max_distance_km ** 2
        mins = self.fit_min_distance_km ** 2

        baseline = (maxs + mins) / 2
        amplitude = (maxs - mins) / 2
        return baseline, amplitude

    @property
    def readings_count(self):
        return StationDistanceReading.query.filter_by(station_pair_id=self.id).count()


class StationDistanceReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    station_pair_id = db.Column(db.ForeignKey('station_pair.id'), nullable=False)
    station_pair = db.relationship('StationPair', backref='readings')

    distance_km = db.Column(db.Integer, nullable=False)
    when = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    travel_time_u = db.Column(db.Integer, nullable=True) # travel time in units

    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')

## Fuel Price Tracking
class FuelPriceReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')
    station_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station = db.relationship('Station')
    when = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    fuel_g = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    price_per_g = db.Column(db.Float, nullable=False)

class FuelPriceStatistics(db.Model):
    station_id = db.Column(db.Integer, primary_key=True)
    station_name = db.Column(db.String(255), nullable=False)
    station_short_name = db.Column(db.String(255))
    station_level = db.Column(db.Integer)
    system_name = db.Column(db.String(255), nullable=False)
    last_reading = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float, nullable=False)
    last_price = db.Column(db.Float, nullable=False)
