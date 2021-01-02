from datetime import datetime, timezone

from sqlalchemy.orm.exc import NoResultFound
from flask import request, jsonify, render_template

from utt.app import app
from utt.gct import as_gct
from utt.util import today
from utt.model import (
    db,
    autovivify,
    get_station,
    Token,
    Item,
    Vendor,
    VendorInventory,
    VendorInventoryItem, 
    VendorItemPriceReading,
)

def linkify(item_slug):
    # TODO: protect against cross-site scripting
    return '<a href="https://taustation.space/item/{}">{}</a>'.format(item_slug, item_slug)

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

    new_timestamp = datetime.utcnow()
    day = today()

    # make sure the inventory is up-to-date
    latest_inventory = VendorInventory.query.filter_by(vendor_id=vendor.id) \
        .order_by(VendorInventory.last_seen.desc()).first()

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

    # check/update item prices
    def price_tuple(d):
        v = d['price']
        return (float(v), None) if d['currency'] == 'credits' else (None, int(v))

    existing_prices = {vipr.item.slug: vipr for vipr in 
        VendorItemPriceReading.query.filter_by(vendor_id=vendor.id, day=day)}

    prices_updated = False
    for d in payload['inventory']:
        slug = d['slug']
        if slug == 'vip-3':
            continue
        credits, bonds = price_tuple(d)
        if slug in existing_prices:
            record = existing_prices[slug]
            if record.price_credits != credits or record.price_bonds != bonds:
                prices_updated = True
                record.price_credits = credits
                record.price_bonds = bonds
                record.token = token
        else:
            db.session.add(VendorItemPriceReading(
                token=token,
                vendor=vendor,
                item=Item.query.filter_by(slug=slug).one(),
                day=day,
                price_credits=credits,
                price_bonds=bonds,
            ))
            prices_updated = True

    if prices_updated:
        messages.append('Price information recorded/updated.')

    db.session.commit()
    
    return jsonify({'recorded': True, 'message': ' '.join(messages)})

