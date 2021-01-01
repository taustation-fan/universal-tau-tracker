from datetime import datetime, timezone

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.gct import as_gct
from utt.model import (
    db,
    autovivify,
    get_station,
    Token,
    Item,
    ItemType,
    ItemRarity,
    ItemAspectWeapon,
    ItemAspectArmor,
    ItemAspectMedical,
    WeaponRange,
    WeaponType,
)

def item_aspect_armor(item, attributes):
    required = ('piercing_defense', 'impact_defense', 'energy_defense')
    for attr in required:
        if attributes.get(attr) is None:
            print('No attribute {}, so not an armor'.format(attr))
            return

    modified_attributes = {k: float(attributes[k]) for k in required}
    if item.aspect_armor:
        for k, v in modified_attributes.items():
            setattr(item.aspect_armor, k, v)
    else:
        item.aspect_armor = ItemAspectArmor(item=item, **modified_attributes)
        db.session.add(item.aspect_armor)

def item_aspect_medical(item, attributes):
    required = ('strength_boost', 'agility_boost', 'stamina_boost', 'intelligence_boost',
                'social_boost', 'base_toxicity')
    for attr in required:
        if attributes.get(attr) is None:
            print('No attribute {}, so not a medical'.format(attr))
            return

    modified_attributes = {k: float(attributes[k]) for k in required}
    if item.aspect_medical:
        for k, v in modified_attributes.items():
            setattr(item.aspect_medical, k, v)
    else:
        item.aspect_medical = ItemAspectMedical(item=item, **modified_attributes)
        db.session.add(item.aspect_medical)


def item_aspect_weapon(item, attributes):
    required = ('accuracy', 'hand_to_hand', 'range', 'weapon_type',
                'piercing_damage', 'impact_damage', 'energy_damage')
    for attr in required:
        if attributes.get(attr) is None:
            print('No attribute {}, so not a weapon'.format(attr))
            return

    modified_attributes = dict(
        weapon_type=autovivify(WeaponType, {'name': attributes['weapon_type']}),
        weapon_range=autovivify(WeaponRange, {'name': attributes['range']}),
        hand_to_hand=attributes['hand_to_hand'],
        piercing_damage=float(attributes['piercing_damage']),
        impact_damage=float(attributes['impact_damage']),
        energy_damage=float(attributes['energy_damage']),
        accuracy=float(attributes['accuracy']),
    )

    if item.aspect_weapon:
        for k, v in modified_attributes.items():
            if v is not None:
                setattr(item.aspect_weapon, v)
        db.session.add(item.aspect_weapon)
    aspect = ItemAspectWeapon(item=item, **modified_attributes)
    db.session.add(aspect)
    print('Weapon aspect added for {}'.format(item.name))
    item.aspect_weapon = aspect

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
    item_aspect_armor(item, payload)
    item_aspect_medical(item, payload)
    item_aspect_weapon(item, payload)
    db.session.commit()

    response = {'id': item.id}

    return jsonify(response)
