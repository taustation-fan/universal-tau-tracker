#!/usr/bin/env python3
import sys
import math
from datetime import datetime, timedelta, timezone

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from utt.model import db, StationPair, StationDistanceReading as SDR
from utt import app
from utt.gct import as_gct



pair_id = int(sys.argv[1])

with app.app_context():
    pair = StationPair.query.filter_by(id=pair_id).one()
    assert pair.fit_period_u is not None, 'No period fit known'
    assert pair.fit_min_distance_km is not None, 'No min distance fit known'
    assert pair.fit_max_distance_km is not None, 'No max distance fit known'
    assert pair.fit_phase is not None, 'No phase fit known'

    start = datetime.now(timezone.utc)
    end  = start + timedelta(days=1)
    readings = SDR.query.filter_by(station_pair_id=pair.id)\
               .filter(SDR.when >=start, SDR.when < end).order_by(SDR.when)
    x = []
    y = []
    for reading in readings:
        x.append(float(as_gct(reading.when, format=False)))
        y.append(float(reading.distance_km))

    xr = np.linspace(float(as_gct(start, format=False)), float(as_gct(end, format=False)), 1000)

    maxs = pair.fit_max_distance_km ** 2
    mins = pair.fit_min_distance_km ** 2

    baseline =(maxs + mins) / 2
    amplitude = (maxs - mins) / 2
    yr = np.sqrt(baseline +  amplitude * np.cos(xr * (2 * np.pi / pair.fit_period_u) + pair.fit_phase))

    plt.plot(xr, yr, 'b-', label='predicted values')

    if len(x) > 2:
        plt.plot(x, y, 'ro', label='Measurement')
    plt.gcf().set_size_inches(12, 9)
    plt.ylabel('Distance/km')
    plt.xlabel('Time/u')
    plt.title(str(pair))
    plt.legend()
    plt.tight_layout()
    plt.show()

