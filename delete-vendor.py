import random
import string
import sys

from utt.model import db, VendorItemPriceReading, VendorInventoryItem, VendorInventory, Vendor
from utt import app
from sqlalchemy.exc import IntegrityError

vendor_id = int(sys.argv[1])

with app.app_context():
    vendor = Vendor.query.filter_by(id=vendor_id).one()
    print('Vendor {} on {}'.format(vendor.name, vendor.station.short))
    VendorItemPriceReading.query.filter_by(vendor_id=vendor_id).delete()
    for vi in VendorInventory.query.filter_by(vendor_id=vendor_id):
        VendorInventoryItem.query.filter_by(vendor_inventory_id=vi.id).delete()
        db.session.delete(vi)
    db.session.delete(vendor)
    
    db.session.commit()
