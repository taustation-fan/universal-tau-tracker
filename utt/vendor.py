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
    Vendor,
    VendorInventory,
    VendorInventoryItem, 
)

def linkify(item_slug):
    # TODO: protect against cross-site scripting
    return '<a href="https://taustation.space/{}">{}</a>'.format(item_slug, item_slug)

@app.route('/v1/vendor-inventory/add', methods=['POST'])
def add_vendory_inventory():
    payload = request.get_json(force=True)
    token = Token.verify(payload['token'])
    token.record_script_version(payload.get('script_version'))

    messages = []

    station = get_station(payload['system'], payload['station'])
    vendor_name = payload['vendor']

    vendor = Vendor.query.filter_by(station_id=station.id, name=vendor_name).first()
    if not vendor:
        messages.append('Vendor created.')
        vendor = Vendor(
            station=station,
            name=vendor_name,
        )
        db.session.add(vendor)

    slugs = {iv['slug'] for iv in payload['inventory']}
    if 'vip-3' in slugs:
        slugs.remove('vip-3')

    items = {item.slug: item for item in Item.query.filter(Item.slug.in_(sorted(slugs)))}
    missing = [slug for slug in slugs if not slug in items]
    if missing:
        return jsonify({
            'recorded': False,
            'message': 'The Tracker does not know about the following item(s): ' + ', '.join(
                [linkify(slug) for slug in missing]
            )
        })

    latest_inventory = VendorInventory.query.filter_by(vendor_id=vendor.id) \
        .order_by(VendorInventory.last_seen.desc()).first()

    new_timestamp = datetime.utcnow()

    if latest_inventory and latest_inventory.item_slugs == slugs:
        # inventory still up to date
        latest_inventory.last_seen = new_timestamp
        messages.append('Updated inventory timestamp.')
    else:
        new_inv = VendorInventory(
            token=token,
            vendor=vendor,
            first_seen=new_timestamp,
            last_seen=new_timestamp,
        )
        messages.append('New inventory state recorded.')
        db.session.add(new_inv)
        for item in items.values():
            db.session.add(VendorInventoryItem(
                vendor_inventory=new_inv,
                item=item,
            ))

    db.session.commit()
    
    return jsonify({'recorded': True, 'message': ' '.join(messages)})

