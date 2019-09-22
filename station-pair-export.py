#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone

from utt.model import db, StationPair
from utt import app
from utt.gct import as_gct

with app.app_context():
    result = []
    for pair in StationPair.query.order_by(StationPair.id):
        if pair.has_full_fit:
            result.append({
                'id': pair.id,
                'fit_period_u': pair.fit_period_u,
                'fit_min_distance_km': pair.fit_min_distance_km,
                'fit_max_distance_km': pair.fit_max_distance_km,
                'fit_phase': pair.fit_phase,
            })

print(json.dumps(result))
