from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from utt.util import today

db = SQLAlchemy()

class InvalidTokenException(Exception):
    def __init__():
        super().__init__('You need a valid token')


def get_station(system_name, station_name, create=True):
    system = System.query.filter(func.lower(System.name)==system_name.lower()).first()
    if not system:
        assert create, 'No such system {}'.format(system_name)
        system = System(name=system_name)
        db.session.add(system)
    station = Station.query.filter(Station.system_id == system.id, Station.name_lower == station_name.lower()).first()
    if not station:
        assert create, 'No such station {} in {} system'.format(station_name, system_name)

        assert not ('Confined to the' in station_name or 'Doing activity' in station_name
                    or 'Hotel Room' in station_name or 'Docking' in station_name), \
            '{} does not look like a proper station name'.format(station_name)
        station = Station(system=system, name=station_name, name_lower=station_name.lower())
        db.session.add(station)
    return station

## General classes
class System(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    rank = db.Column(db.Integer)

    __mapper_args__ = {'order_by': ['rank', 'name']}


class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.ForeignKey('system.id'), nullable=False)
    system = db.relationship('System', backref='stations')
    name = db.Column(db.String(200), unique=True, nullable=False)
    short = db.Column(db.String())
    name_lower = db.Column(db.String(200), unique=True, nullable=False)
    fit_radius_km = db.Column(db.Float)
    fit_period_u = db.Column(db.Float)
    # fit_phase = db.Column(db.Float)

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    last_script_version = db.Column(db.String())

class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(80), unique=True, nullable=False)
    infotext = db.Column(db.String(250))
    character_id = db.Column(db.ForeignKey('character.id'), nullable=False)
    character = db.relationship('Character', backref=db.backref('tokens', lazy=True))
    full_read_permission = db.Column(db.Boolean(), nullable=False, default=False)

    @classmethod
    def verify(cls, token):
        try:
            return cls.query.filter_by(token=token).one()
        except NoResultFound:
            raise InvalidTokenException()


    def record_script_version(self, version):
        if version is None:
            version = 'pre 1.7'
        self.character.last_script_version = str(version);

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

class FuelPriceEstimation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station = db.relationship('Station')
    day = db.Column(db.Date, nullable=False)
    price_per_g = db.Column(db.Float, nullable=False)

    @classmethod
    def all_today(cls):
        return cls.query.filter(cls.day == today()).order_by(cls.price_per_g.asc())

    @classmethod
    def today_as_dict(cls):
        return {e.station.short: e.price_per_g for e in cls.all_today()}

class FuelPriceStatistics(db.Model):
    station_id = db.Column(db.ForeignKey('station.id'), primary_key=True, )
    station = db.relationship('Station')
    station_name = db.Column(db.String(255), nullable=False)
    station_short_name = db.Column(db.String(255))
    station_level = db.Column(db.Integer)
    system_name = db.Column(db.String(255), nullable=False)
    system_rank = db.Column(db.Integer)
    last_reading = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float, nullable=False)
    last_price = db.Column(db.Float, nullable=False)


class ShipClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True, nullable=False)

    key = 'name'

class Ship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration = db.Column(db.String(), nullable=False, unique=True)
    name = db.Column(db.String(), nullable=False)
    captain = db.Column(db.String(), nullable=False)
    ship_class_id = db.Column(db.ForeignKey('ship_class.id'), nullable=False)
    ship_class = db.relationship('ShipClass')
    sightings = db.relationship('ShipSighting', order_by='asc(ShipSighting.when)')

    key = 'registration'

    @property
    def last_sighting(self):
        return ShipSighting.query.filter_by(ship_id=self.id).order_by(ShipSighting.when.desc()).first()

    @property
    def last_movement(self):
        ls = self.last_sighting
        if ls is None:
            return None
        previous = ShipSighting.query.filter_by(ship_id=self.id).filter(ShipSighting.station_id != ls.station_id) \
            .order_by(ShipSighting.when.desc()).first()
        if previous:
            return previous.when

    @property
    def sighting_streaks(self):
        cached = getattr(self, '_sighting_streaks', None)
        if cached is not None:
            return cached
        streaks = []
        current = []
        for s in self.sightings:
            if not current:
                pass
            elif current[-1].station_id != s.station_id:
                streaks.append(ShipSightingStreak(current))
                current = []
            current.append(s)
        if current:
            streaks.append(ShipSightingStreak(current))
        self._sighting_streaks = streaks
        return streaks

    @property
    def min_jumps(self):
        ss = self.sighting_streaks
        if not ss:
            return 0
        c = 0
        previous_system_id = ss[0].station.system_id
        for streak in ss[1:]:
            if streak.station.system_id != previous_system_id:
                c += 1
                previous_system_id = streak.station.system_id
        return c

    @property
    def siblings(self):
        return Ship.query.filter(Ship.captain == self.captain, Ship.id != self.id)


class ShipSightingStreak:
    def __init__(self, sightings):
        assert len(sightings) > 0, 'Empty streak makes no sense'
        self.sightings = sightings

    @property
    def station(self):
        return self.sightings[0].station

    @property
    def ship(self):
        return self.sightings[0].ship

    @property
    def first(self):
        return self.sightings[0]

    @property
    def last(self):
        return self.sightings[-1]

class ShipSighting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.ForeignKey('ship.id'), nullable=False)
    ship = db.relationship('Ship')
    station_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station = db.relationship('Station')
    when = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')

def autovivify(model, attrs, update=False):
    """
    Tries to look up if an object matching the attributes in dict `attrs` exist.
    If not, creates and returns a new object.
    """
    key_col = model.key
    key_val = attrs[key_col]

    try:
        result = model.query.filter(getattr(model, key_col) == key_val).one()
        if update:
            for k, v in attrs.items():
                if v is not None:
                    setattr(result, k, v)
        return result
    except NoResultFound:
        pass
    print('autovivify: creating new {}'.format(model))
    new = model(**attrs)
    db.session.add(new)
    return new

class Genotype(db.Model):
    """
    Gemontype: Baseline, Colonist, Belter, ...
    Currently used for food, maybe will have other uses later
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'

class Stat(db.Model):
    """
    Stat: Strength, Agility, ...
    Currently used for food, maybe will have other uses later
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'


class ItemType(db.Model):
    """
    Item type: Weapon, Armor, VIP, Blueprint etc.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'

class ItemRarity(db.Model):
    """
    Item Rarity: common, uncommon, rare, epic
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'

class WeaponType(db.Model):
    """
    Weapon Type: Hand Gun, Balde etc.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'

class WeaponRange(db.Model):
    """
    Weapon Range: Short, Long
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    key = 'name'

class Item(db.Model):
    key = 'name'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), index=True, nullable=False, unique=True)
    slug = db.Column(db.String(200), index=True, unique=True)
    mass_kg = db.Column(db.Float, nullable=False)
    tier = db.Column(db.Integer, nullable=False)

    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')

    item_type_id = db.Column(db.ForeignKey('item_type.id'), nullable=False)
    item_type = db.relationship('ItemType')
    rarity_id = db.Column(db.ForeignKey('item_rarity.id'), nullable=False)
    rarity = db.relationship('ItemRarity')

    description = db.Column(db.Text)

    # not the daily and station-dependent value, but rather the one shown for example
    # in Storage
    intrinsic_value_credits = db.Column(db.Float)
    intrinsic_value_bonds = db.Column(db.Integer)

    aspect_weapon = db.relationship('ItemAspectWeapon', back_populates='item', uselist=False)
    aspect_armor = db.relationship('ItemAspectArmor', back_populates='item', uselist=False)
    aspect_medical = db.relationship('ItemAspectMedical', back_populates='item', uselist=False)
    aspect_food = db.relationship('ItemAspectFood', back_populates='item', uselist=False)
    
    @property
    def aspects(self):
        return [a for a in (
            self.aspect_armor,
            self.aspect_medical,
            self.aspect_food,
            self.aspect_weapon,
        ) if a is not None]

    def as_json(self):
        result = {
            'slug': self.slug,
            'name': self.name,
            'type': self.item_type.name,
            'rarity': self.rarity.name,
            'description': self.description,
        }
        for aspect in self.aspects:
            result.update(**aspect.as_json())
        return result

    @property
    def min_vendor_price_reading(self):
        return VendorItemPriceReading.query.filter_by(item_id=self.id).order_by(
            VendorItemPriceReading.price_credits.asc(),
            VendorItemPriceReading.price_bonds.asc(),
        ).first()

    @property
    def max_vendor_price_reading(self):
        return VendorItemPriceReading.query.filter_by(item_id=self.id).order_by(
            VendorItemPriceReading.price_credits.desc(),
            VendorItemPriceReading.price_bonds.desc(),
        ).first()
class ItemAspectWeapon(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.ForeignKey('item.id'), nullable=False, unique=True)
    item = db.relationship('Item')

    weapon_type_id = db.Column(db.ForeignKey('weapon_type.id'), nullable=False)
    weapon_type = db.relationship('WeaponType')

    weapon_range_id = db.Column(db.ForeignKey('weapon_range.id'), nullable=False)
    weapon_range = db.relationship('WeaponRange')

    hand_to_hand = db.Column(db.Boolean, nullable=False)

    accuracy = db.Column(db.Float, nullable=False)
    piercing_damage = db.Column(db.Float, nullable=False)
    impact_damage = db.Column(db.Float, nullable=False)
    energy_damage = db.Column(db.Float, nullable=False)

    def as_json(self):
        return {
            'weapon_type': self.weapon_type.name,
            'weapon_range': self.weapon_range.name,
            'hand_to_hand': self.hand_to_hand,
            'accuracy': self.accuracy,
            'piercing_damage': self.piercing_damage,
            'impact_damage': self.impact_damage,
            'energy_damage': self.energy_damage,
        }


class ItemAspectArmor(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.ForeignKey('item.id'), nullable=False, unique=True)
    item = db.relationship('Item')

    piercing_defense = db.Column(db.Float, nullable=False)
    impact_defense = db.Column(db.Float, nullable=False)
    energy_defense = db.Column(db.Float, nullable=False)

    def as_json(self):
        return {
            'piercing_defense': self.piercing_defense,
            'impact_defense': self.impact_defense,
            'energy_defense': self.energy_defense,
        }

class ItemAspectMedical(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.ForeignKey('item.id'), nullable=False, unique=True)
    item = db.relationship('Item')

    base_toxicity = db.Column(db.Float, nullable=False)
    strength_boost = db.Column(db.Float, nullable=False)
    agility_boost = db.Column(db.Float, nullable=False)
    stamina_boost = db.Column(db.Float, nullable=False)
    social_boost = db.Column(db.Float, nullable=False)
    intelligence_boost = db.Column(db.Float, nullable=False)

    def as_json(self):
        return {
            'base_toxicity': self.base_toxicity,
            'strength_boost': self.strength_boost,
            'agility_boost': self.agility_boost,
            'stamina_boost': self.stamina_boost,
            'social_boost': self.social_boost,
            'intelligence_boost': self.intelligence_boost,
        }

class FoodEffectSize(db.Model):
    """
    Food effect size: large, small
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True, nullable=False)

    key = 'name'

class ItemAspectFood(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.ForeignKey('item.id'), nullable=False, unique=True)
    item = db.relationship('Item')

    genotype_id = db.Column(db.ForeignKey('genotype.id'), nullable=False)
    genotype = db.relationship('Genotype')

    affected_stat_id = db.Column(db.ForeignKey('stat.id'), nullable=False)
    affected_stat = db.relationship('Stat')

    effect_size_id = db.Column(db.ForeignKey('food_effect_size.id'), nullable=False)
    effect_size = db.relationship('FoodEffectSize')

    duration_segments = db.Column(db.Integer, nullable=False, default=1)

    def as_json(self):
        return {
            'genotype':      self.genotype.name,
            'affected_stat': self.affected_stat.name,
            'effect_size':   self.effect_size.name,
            'duration_segments': self.duration_segments,
        }


class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.ForeignKey('station.id'), nullable=False)
    station = db.relationship('Station')
    name = db.Column(db.String(200), nullable=False)
    __table_args__ = (
        db.UniqueConstraint('station_id', 'name'),
    )

class VendorInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.ForeignKey('vendor.id'), nullable=False)
    vendor = db.relationship('Vendor')
    first_seen = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')
    is_current = db.Column(db.Boolean, nullable=False, default=True)

    inventory_items = db.relationship('VendorInventoryItem', back_populates='vendor_inventory')

    @property
    def item_slugs(self):
        return {i.item.slug for i in self.inventory_items if i.item.slug is not None}

class VendorInventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_inventory_id = db.Column(db.ForeignKey('vendor_inventory.id'), nullable=False)
    vendor_inventory = db.relationship('VendorInventory')
    item_id = db.Column(db.ForeignKey('item.id'), nullable=False)
    item = db.relationship('Item')

    __table_args__ = (
        db.UniqueConstraint('vendor_inventory_id', 'item_id'),
    )

class VendorItemPriceReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.ForeignKey('vendor.id'), nullable=False)
    vendor = db.relationship('Vendor')
    item_id = db.Column(db.ForeignKey('item.id'), nullable=False)
    item = db.relationship('Item')
    token_id = db.Column(db.ForeignKey('token.id'), nullable=False)
    token = db.relationship('Token')

    day = db.Column(db.Date, nullable=False)
    price_credits = db.Column(db.Float)
    price_bonds = db.Column(db.Integer)

    __table_args__ = (
        db.UniqueConstraint('vendor_id', 'item_id', 'day'),
    )
