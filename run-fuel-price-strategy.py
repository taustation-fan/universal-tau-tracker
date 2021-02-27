#!/usr/bin/env python3
import argparse
import json
import math
import requests
import sys
import urllib.request

from bs4 import BeautifulSoup
from sqlalchemy.orm.exc import NoResultFound

from utt.model import db, Station, FuelPriceEstimation
from utt.util import today
from utt import app

from diskcache import Cache
from datetime import date


DEBUG = False
verbose = False


def write_fuel_prices(prices, date=None):
    if date is None:
        date = today()
    # delete old data for today
    FuelPriceEstimation.query.filter_by(day=date).delete()

    # add new data for today
    for station_name, price in prices.items():
        if verbose:
            print('Writing data for {}'.format(station_name))
        try:
            station = Station.query.filter_by(name=station_name).one()
            est = FuelPriceEstimation(
                station=station,
                day=date,
                price_per_g=price,
            ) 
            db.session.add(est)
        except NoResultFound:
            print('Found no station {}'.format(station_name))
            
    db.session.commit()

INTERVAL_THRESHOLD = 0.5


def debug_print(*msg):
    if DEBUG:
        sys.stderr.write(" ".join(map(str, msg)) + "\n")


def _get_minmax(slug):
    url = "https://taustation.space/item/" + slug
    req = requests.get(url)
    if req.status_code != 200:
        raise Exception('Cannot get {}: {}'.format(url, req.text))
    phtml = BeautifulSoup(req.text, "lxml")
    tag = phtml.body.find('span', attrs={'class':"currency"})
    children = list(tag.children)
    price_range = children[0]
    a,b = price_range.split(" - ")
    mn = float(a)
    mx = float(b)
    return (mn,mx)

def get_minmax(cache, slug):
    day = str(date.today())
    cache_key = '{}/{}'.format(day, slug)
    result = cache.get(cache_key)
    if result:
        return result
    result = _get_minmax(slug)
    cache.set(cache_key, result)
    return result


def read_items(jsondata):
    """Read the vendor entries from the given JSON data."""
    entries = []
    for station_info in jsondata:
        station = station_info['station']['name']
        system  = station_info['station']['system']
        if station_info.get('missing_data', False):
            print("incomplete data on %s (%s)" % (station, system))
            return []
        fuelprice = station_info['fuel_price_per_g']
        for (vendor,inventory) in station_info['vendors'].items():
            for (slug,itemprice) in inventory.items():
                entry = {
                    'slug'     : slug,
                    'ItemPrice': itemprice,
                    'Vendor'   : vendor,
                    'Station'  : station,
                    'System'   : system,
                    'FuelPrice': fuelprice,
                    'FuelPriceCoefficient': itemprice/fuelprice
                }
                entries.append(entry)
    return entries


def entries_by_key(entries, key):
    """Collect entries by the given key."""
    collected_entries = {}
    for e in entries:
        k = e[key]
        if not k in collected_entries:
            collected_entries[k] = []
        collected_entries[k].append(e)
    return collected_entries

def median(numbers):
    """
    Returns the median of a list of already sorted numbers.
    """
    l = len(numbers)
    if l % 2 == 1:
        return numbers[ l // 2 + 1]
    else:
        return (numbers[l // 2] + numbers[l // 2 + 1]) / 2

def find_most_common_number(l, ACCURACY=0.05):
    """
    In a list of numbers, find one number that is the most common,
    barring some wiggle room for inaccuracies.
    Returns the most common number, or None if there is not one
    clear most common number.
    """
    previous = None
    current_streak = []
    streaks = []
    for n in sorted(l):
        if previous is None:
            previous = n
            current_streak = [n]
            continue
        diff = (n - previous) / n
        if diff <= ACCURACY:
            current_streak.append(n)
        else:
            streaks.append(current_streak)
            current_streak = [n]
        previous = n
    streaks.append(current_streak)

    sorted_streaks = sorted(streaks, key=lambda s: -len(s))
    winning_streak = sorted_streaks[0]

    if len(winning_streak) == 1:
        # seems we have no similar numbers at all
        return None
    if len(sorted_streaks) > 1 and (len(winning_streak) - len(sorted_streaks[1])) < 3:
        # we have two clusters of similar numbers with the same size,
        # so don't assume we have a winner
        return None

    return median(winning_streak)


class Interval:
    def __init__(self):
        self.min = -math.inf
        self.max = math.inf
        self.prices_seen = []

    def update(self, a, b):
        self.prices_seen.append(a)
        self.prices_seen.append(b)
        if a > self.min:
            self.min = a
        if b < self.max:
            self.max = b

    def guess(self):
        return find_most_common_number(self.prices_seen)
        

    def length(self):
        return (self.max - self.min)
    def is_converged(self):
        return self.length() < INTERVAL_THRESHOLD
    def __str__(self):
        return "[%.2f, %.2f]" % (self.min, self.max)
    def midpoint(self):
        return 0.5 * (self.min + self.max)


def get_fuel_prices(cache, strategy_file=None):
    if strategy_file is not None:
        with open(strategy_file) as f:
            stations_json = json.load(f)
    else:
        url = "https://tracker.tauguide.de/v1/special/fuel-vendor-correlation"
        with urllib.request.urlopen(url) as response:
            stations_json = json.load(response)

    entries = read_items(stations_json)
    if not entries:
        print("Not enough data, giving up")
        sys.exit(1)
    # each entry has: slug, ItemPrice, Vendor, Station, System, FuelPrice, FuelPriceCoefficient

    # map stations to short names
    shortname_by_station = { info['station']['name'] : info['station']['short'] for info in stations_json }

    # get list of stations (having vendors), and entries available per station
    stations = set( e['Station'] for e in entries)
    entries_by_station = entries_by_key(entries, 'Station')

    # for each slug, get the list of stations where it is available
    available_on_station_by_slug = {}
    for entry in entries:
        slug = entry['slug']
        station = entry['Station']
        if not slug in available_on_station_by_slug:
            available_on_station_by_slug[slug] = set()
        available_on_station_by_slug[slug].add(station)

    # run over all stations
    fuelprice_by_station = {}
    for station in stations:

        debug_print("STATION =", station)
        # collect vendor entries for this station
        station_entries = entries_by_station[station]
        # get items available on this station
        station_entries_by_slug = entries_by_key(station_entries, 'slug')
        debug_print("  items available: ", len(station_entries_by_slug))
        # remove slugs with ambiguous pricing
        cleaned_entries = {}
        for slug, slug_entries in station_entries_by_slug.items():
            if len(slug_entries) != 1:
                prices = set(e['ItemPrice'] for e in slug_entries)
                if len(prices) != 1:
                    debug_print("  ambiguous pricing: discarding '%s' on %s" % (slug, station))
                    continue
            cleaned_entries[slug] = slug_entries
        station_entries_by_slug = cleaned_entries
        debug_print("  items left: ", len(station_entries_by_slug))

        # sort slugs by low availabilty, then high price
        station_slugs = list(station_entries_by_slug.keys())
        station_slugs.sort(key = lambda slug: station_entries_by_slug[slug][0]['ItemPrice'], reverse=True)
        station_slugs.sort(key = lambda slug: len(available_on_station_by_slug[slug]))

        fuelprice_interval = Interval()
        station_combinations = []
        for slug in station_slugs:
            # if this item is available on other stations...
            if len(available_on_station_by_slug[slug]) > 1:
                # then check if this combination of stations has already been considered previously
                station_combination = "++".join(sorted(available_on_station_by_slug[slug]))
                if station_combination in station_combinations:
                    debug_print("  skip '%s', no new station combination" % slug)
                    continue # no new combination, move on to next item
                station_combinations.append(station_combination)

            fpc = station_entries_by_slug[slug][0]['FuelPriceCoefficient']
            itemprice_min, itemprice_max = get_minmax(cache, slug)
            fuelprice_min = itemprice_min / fpc
            fuelprice_max = itemprice_max / fpc
            fuelprice_interval.update(fuelprice_min, fuelprice_max)
            debug_print("  after '%s': fuelprice = %s" % (slug, fuelprice_interval))
            if fuelprice_interval.is_converged():
                debug_print("  converged!")
                break

        # store result
        fuelprice_by_station[station] = fuelprice_interval
            
    # sort stations by fuelprice midpoint
    result = {}
    for station in sorted(stations, key = lambda station: fuelprice_by_station[station].midpoint() ):
        fp = fuelprice_by_station[station]
        if fp.is_converged():
            result[station] = fp.midpoint()
        else:
            guess = fp.guess()
            if guess is not None:
                result[station] = guess
                fuel_string = '%.2f (guessed by frequency)' % guess
            else:
                fuel_string = str(fp)
    return result


if __name__ == '__main__':
    # verbose flag?
    parser = argparse.ArgumentParser(description='Tau Station Fuel Price Estimator, based on a model by Sotheryn and code by SandwichMaker')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--write', action='store_true')
    options = parser.parse_args()

    if options.verbose:
        verbose = True
    if options.debug:
        verbose = True
        DEBUG = True

    with Cache(directory='item-price-cache') as cache:
        fuel_prices = get_fuel_prices(cache)

    # print result
    if verbose:
        stations_ascending = sorted(fuel_prices.keys(), key = lambda k: fuel_prices[k])
        for station in stations_ascending:
            print("%8.2f  %s" % (fuel_prices[station], station))

    if options.write:
        with app.app_context():
            write_fuel_prices(fuel_prices)
