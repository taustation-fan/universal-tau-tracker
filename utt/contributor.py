from collections import defaultdict
from flask import request, jsonify, render_template
from sqlalchemy import func

from utt.app import app
from utt.model import db, \
    CareerBatchSubmission, \
    Character, \
    FuelPriceReading, \
    ShipSighting, \
    StationDistanceReading, \
    Token

@app.route('/contributor')
def contributor_statistics():
    token_to_character = {}
    for t in Token.query.all():
        token_to_character[t.id] = t.character.name

    pairs = (
        ('career', CareerBatchSubmission),
        ('fuel', FuelPriceReading),
        ('ship', ShipSighting),
        ('distance', StationDistanceReading),
    )
    
    counts = defaultdict(lambda: defaultdict(int))
    for name, model in pairs:
        attr = model.token_id
        q = db.session.query(attr, func.count()).group_by(attr)
        for token_id, count in q:
            character = token_to_character[token_id]
            counts[character][name] += count
    return render_template('contributor/overview.html', contributors=counts)
        
    
