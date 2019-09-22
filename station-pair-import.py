#!/usr/bin/env python3
import sys
import json
from datetime import datetime, timedelta, timezone

from utt.model import db, StationPair
from utt import app
from utt.gct import as_gct

filename = sys.argv[1]
with open(filename) as f:
    data = json.load(f)

with app.app_context():
    for record in data:
        pair = StationPair.query.filter_by(id=record.pop('id')).first()
        if not pair:
            continue
        for k, v in record.items():
            setattr(pair, k, v)
    db.session.commit()
