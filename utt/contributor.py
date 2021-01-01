from collections import defaultdict
from flask import request, jsonify, render_template
from sqlalchemy import func

from utt.app import app
from utt.model import db, \
    CareerBatchSubmission, \
    Character, \
    FuelPriceReading, \
    Item, \
    ShipSighting, \
    StationDistanceReading, \
    Token

@app.route('/contributor')
def contributor_statistics():
    token_to_character = {}
    contributors = defaultdict(lambda: defaultdict(int))
    for t in Token.query.all():
        token_to_character[t.id] = t.character.name
        if t.character.last_script_version:
            contributors[t.character.name]['last_script_version'] = t.character.last_script_version

    pairs = (
        ('career', CareerBatchSubmission),
        ('fuel', FuelPriceReading),
        ('ship', ShipSighting),
        ('distance', StationDistanceReading),
        ('item', Item),
    )
    
    for name, model in pairs:
        attr = model.token_id
        q = db.session.query(attr, func.count()).group_by(attr)
        for token_id, count in q:
            character = token_to_character[token_id]
            contributors[character][name] += count
    return render_template('contributor/overview.html', contributors=contributors)
        
    
