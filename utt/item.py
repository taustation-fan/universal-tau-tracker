from datetime import datetime, timezone

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.gct import as_gct
from utt.model import db, \
    autovivify, \
    get_station, \
    Token, \
    Item, \
    ItemType, \
    ItemRarity, \
    ItemAspectWeapon, \
    WeaponType

def item_aspect_weapon(item, attributes):
    if item.aspect_weapon:
        # TODO: update attributes?
        return
    required = ('accuracy', 'hand_to_hand', 'long_range', 'weapon_type',
                'piercing_damage', 'impact_damage', 'energy_damage')
    # TODO

@app.route('/v1/item/add', methods=['POST'])
def item_add():
    payload = request.get_json(force=True)
    token = Token.verify(payload['token'])
    token.record_script_version(payload.get('script_version'))
    item = autovivify(Item, {
        'token': token,
        'name': payload['name'],
        'slug': payload.get('slug'),
        'mass_kg': float(payload['mass_kg']),
        'tier': payload['tier'],
        'rarity': autovivify(ItemRarity, dict(name=payload['rarity'])),
        'item_type': autovivify(ItemType, dict(name=payload['type'])),
        'description': payload.get('description'),
    })
    db.session.commit()

    response = {'id': item.id}

    return jsonify(response)
