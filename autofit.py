#!/usr/bin/env python3
import sys
import math
import argparse

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from astropy.timeseries import LombScargle

from utt.model import db, StationPair, StationDistanceReading as SDR
from utt import app
from utt.gct import as_gct

def parse_args():
    parser = argparse.ArgumentParser(description='Automatic fitting of station pair data')
    parser.add_argument('--improve', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('station_id', type=int, nargs='?')

    return parser.parse_args()

options = parse_args()
if options.all:
    options.improve = True
else:
    assert options.station_id, 'Need --all or station_id'



def improve_one(pair, interactive=True):
    readings = SDR.query.filter_by(station_pair_id=pair.id).order_by(SDR.when)

    x = []
    y = []
    for reading in readings:
        x.append(float(as_gct(reading.when, format=False)))
        y.append(float(reading.distance_km * reading.distance_km))

    min_y = min(y)
    max_y = max(y)
    baseline = (min_y + max_y) / 2
    amplitude = (max_y - min_y) / 2
    if pair.fit_min_distance_km is not None and pair.fit_max_distance_km is not None:
        baseline, amplitude = pair.baseline_amptlitude_pair

    if pair.fit_period_u:
        period = pair.fit_period_u
        fudge_factor = 2
    else:
        plt.gcf().set_size_inches(12, 9)
        plt.title(str(pair))
        plt.plot(x, y, 'ro-')
        plt.show()
        count_periods = float(input('Rough number of periods in the plot: '))
        period = (max(x) - min(x))/ count_periods
        fudge_factor = 10
    phase = pair.fit_phase or 0.0

    est_freq = 1 / period
    freqs = np.linspace(est_freq / fudge_factor, est_freq * fudge_factor, 1600)
    
    power = LombScargle(x, y).power(freqs)
    period = 1/freqs[np.argmax(power)]
    print('Period determined by LS: ', period)

    # prepare for least-squares curve fit
    def f(x, period, amplitude, baseline, phase):
        if amplitude > baseline:
            return 1e20
        return np.cos(np.array(x) * (2 * np.pi / period) + phase) * amplitude + baseline

    initial = [period, amplitude, baseline, phase]
    lower = [0.5 *  period, 0.8 * amplitude, 0.5 * baseline, - 21 * np.pi]
    upper = [2.0 * period,  10 * amplitude, 10 * baseline, 21 * np.pi ]
    fit_result, prec = curve_fit(f, x, y, initial, bounds=[lower, upper])
    print(fit_result)
    min_distance = math.sqrt(fit_result[2] - fit_result[1])
    max_distance = math.sqrt(fit_result[2] + fit_result[1])
    print(prec)
    print('Curve fit results: period = {:.2f} u, radius = [{:.2f} {:.2f}] km'.format(
        fit_result[0],
        min_distance,
        max_distance))

    phase = fit_result[3]
    tau = 2 * np.pi
    while phase > tau:
        phase -= tau
    while phase < 0:
        phase += tau

    if options.improve and pair.has_full_fit:
        def close(a, b):
            return (a-b)/b <= 0.01

        small_difference = all((
            close(fit_result[0], pair.fit_period_u),
            close(pair.fit_min_distance_km, min_distance),
            close(pair.fit_max_distance_km, max_distance),
            close(pair.fit_phase, phase),
        ))
        if small_difference:
            print('Detected only small difference, writing automatically')
            pair.fit_period_u = fit_result[0]
            pair.fit_min_distance_km = min_distance
            pair.fit_max_distance_km = max_distance
            pair.fit_phase = phase
            return True
        
    if not interactive:
        return False
    # regularized grid for plotting
    xr = np.linspace(min(x), max(x), 50 * len(x))
    plt.plot(xr, f(xr, *fit_result), 'b-')
    
    plt.gcf().set_size_inches(12, 9)
    plt.title(str(pair))
    plt.plot(x, y, 'ro')
    plt.show()

    if input('Write (y/n)? ') == 'y':
        pair.fit_period_u = fit_result[0]
        pair.fit_min_distance_km = min_distance
        pair.fit_max_distance_km = max_distance
        pair.fit_phase = phase
        db.session.commit()
        print('... saved. Bye.')

with app.app_context():
    if options.all:
        failed = []
        for pair in StationPair.query:
            success = improve_one(pair, interactive=False)
            if not success:
                failed.append(pair)
        if failed:
            print('\n\nFAILED:')
            for pair in failed:
                print('   {}  {}'.format(pair.id, pair))
            
    else:
        pair = StationPair.query.filter_by(id=options.station_id).one()
        improve_one(pair)

    if options.improve:
        db.session.commit()

