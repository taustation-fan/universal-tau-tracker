#!/usr/bin/env python3
import csv
import requests
import sys
import argparse

from bs4 import BeautifulSoup
from sqlalchemy.orm.exc import NoResultFound

from utt.model import db, Station, FuelPriceEstimation
from utt.util import today
from utt import app


verbose = False


def read_strategy(fname):
    with open(fname) as fp:
        cr = csv.DictReader(fp)
        strats = list(cr)
    return strats


def get_minmax(slug):
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


def is_close(a,b):
    tolerance = 0.02
    return abs(a/b - 1.0) < tolerance


def run_strategy(strat, fuel_prices):
    station = strat['Station']
    slug = strat['slug']
    fpc = float(strat['FuelPriceCoefficient'])
    other_station = strat['OtherStation']
    other_fpc = float(strat['OtherFPC'])
    itemprice_min, itemprice_max = get_minmax(slug)
    if not other_station:
        # if no comparison station, price should be unique
        if itemprice_min != itemprice_max:
            print("FATAL: item price for '%s' is not unique but %f--%f" % (slug, itemprice_min, itemprice_max))
            sys.exit(1)
        itemprice = itemprice_min
        if verbose:
            print("%s: using '%s', price=%.2f, fpc=%.5f => fuelprice=%.2f"
                % (station, slug, itemprice, fpc, itemprice / fpc))
    else:
        # estimate the item price on the comparison station
        if verbose:
            print("%s: using '%s', price=%.2f-%.2f, fpc=%.5f"
                % (station, slug, itemprice_min, itemprice_max, fpc))
            blank = " " * len(station)
        itemprice_other = fuel_prices[other_station] * other_fpc
        if verbose:
            print("%s  comparing with %s with fpc=%.5f, estimated price %.2f"
                % (blank, other_station, other_fpc, itemprice_other))
        if is_close(itemprice_other, itemprice_min):
            itemprice = itemprice_max
            if verbose:
                print("%s  other station's price matches minimum => price=%.2f => fuelprice=%.2f"
                    % (blank, itemprice, itemprice / fpc))
        elif is_close(itemprice_other, itemprice_max):
            itemprice = itemprice_min
            if verbose:
                print("%s  other station's price matches maximum => price=%.2f => fuelprice=%.2f"
                    % (blank, itemprice, itemprice / fpc))
        else:
            print("FATAL: other station's item price for slug '%s' is %f, can't reconcile with %f--%f"
                % (slug, itemprice_other, itemprice_min, itemprice_max))
            sys.exit(1)
    # item price resolved, now calcuate fuel price
    fp = itemprice / fpc
    # store result
    fuel_prices[station] = fp

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


if __name__ == '__main__':
    # verbose flag?
    parser = argparse.ArgumentParser(description='Tau Station Fuel Price Estimator, based on a model by Sotheryn and code by SandwichMaker')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--write', action='store_true')
    options = parser.parse_args()

    if options.verbose:
        verbose = True
    strategies = read_strategy("fuel-price-strategy.csv")
    fuel_prices = {}
    for strat in strategies:
        run_strategy(strat, fuel_prices)

    # print result
    if verbose: print()
    stations_ascending = sorted(fuel_prices.keys(), key = lambda k: fuel_prices[k])
    for station in stations_ascending:
        print("%8.2f  %s" % (fuel_prices[station], station))

    if options.write:
        with app.app_context():
            write_fuel_prices(fuel_prices)
