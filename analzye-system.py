#!/usr/bin/env python3
import sys
import math
from collections import defaultdict
import argparse

from prettytable import PrettyTable
import numpy as np
from scipy.optimize import leastsq

from utt.model import db, System, StationPair
from utt import app
from utt.gct import as_gct

def parse_args():
    parser = argparse.ArgumentParser(description='Find station fit params for a system')
    parser.add_argument('--write', action='store_true')
    parser.add_argument('system_id', type=int)
    return parser.parse_args()

options = parse_args()

system_id = options.system_id

def fmt(number):
    return '{:.2f}'.format(number)

def find_similar_numbers(l):
    previous = None
    current_streak = []
    streaks = []
    for n in sorted(l):
        if previous is None:
            previous = n
            current_streak = [n]
            continue
        diff = (n - previous) / n
        if diff <= 0.005:
            current_streak.append(n)
        else:
            streaks.append(current_streak)
            current_streak = [n]
        previous = n
    streaks.append(current_streak)

    winning_streak = sorted(streaks, key=lambda s: -len(s))[0]
    assert len(winning_streak) > 1, 'Cannot find a non-trivial streak'
    avg = np.average(winning_streak)
    sorted_by_proximty = sorted(l, key=lambda n: abs(n - avg))
    post_filtered_streak = sorted_by_proximty[0:len(l)//2]
    return post_filtered_streak
        

with app.app_context():
    system = System.query.filter_by(id=system_id).one()
    pairs = StationPair.query.filter(StationPair.system_id == system.id, StationPair.fit_period_u != None)
    by_station_id = defaultdict(list)
    relative_period = defaultdict(dict)
    station_by_id = dict()
    print('{} system, {} pairs'.format(system.name, pairs.count()))
    radius_by_id = dict()

    for pair in pairs:
        radii = [(pair.fit_max_distance_km - pair.fit_min_distance_km) / 2,
                 (pair.fit_max_distance_km + pair.fit_min_distance_km) / 2]
        station_by_id[pair.station_a_id] = pair.station_a
        station_by_id[pair.station_b_id] = pair.station_b
        by_station_id[pair.station_a_id] += radii
        by_station_id[pair.station_b_id] += radii
        relative_period[pair.station_a_id][pair.station_b_id] = pair.fit_period_u
        relative_period[pair.station_b_id][pair.station_a_id] = pair.fit_period_u

    for station_id, radii in by_station_id.items():
        similar = find_similar_numbers(radii)
        avg = np.average(similar)
        std = np.std(similar)
        radius_by_id[station_id] = (avg, std)

    station_ids = sorted(station_by_id.keys(), key=lambda x: radius_by_id[x][0])
    all_periods = [pair.fit_period_u for pair in pairs]
    initial = np.linspace(np.min(all_periods), np.max(all_periods), len(station_ids))
    # initial = [752e3, 1184e3, 2308e3, 4197e3]

    def metric(times):
        result = []
        for i in range(0, len(station_ids) - 1):
            for j in range(i + 1, len(station_ids)):
                try:
                    t = relative_period[station_ids[i]][station_ids[j]]
                except KeyError:
                    continue
                result.append( 1 / (1/times[i] - 1/times[j]) - t)
                result.append( 1e6 * (
                    times[i] ** 2 / radius_by_id[station_ids[i]][0] ** 3 \
                  - times[j] ** 2 / radius_by_id[station_ids[j]][0] ** 3
                ))
        return result

    fit_result, _ = leastsq(metric, initial, maxfev=10000 * len(station_ids), ftol=1e-7, xtol=1e-5)

    fit_error = np.average(np.abs(metric(fit_result)))
    period_by_station_id = {station_ids[i]: fit_result[i] for i in range(len(station_ids))}

    print('Fit error: {}'.format(fmt(fit_error)))

    table = PrettyTable(['Station', 'Distance/km', 'Error %', 'Period/u', 'T²/r³'])
    table.align = 'r'
    table.align['Station'] = 'l'

    
    for station_id in station_ids:
        avg, std = radius_by_id[station_id]
        station = station_by_id[station_id]
        station.fit_radius_km = avg
        table.add_row([
            station.name, 
            fmt(avg),
            fmt(std/avg * 100.0),
            fmt(period_by_station_id[station_id]),
            fmt(period_by_station_id[station_id]**2/avg**3),
        ])
        if options.write:
            station.fit_radius_km = avg
            station.fit_period_u = period_by_station_id[station_id]
    print(table)
    if options.write:
        db.session.commit()
