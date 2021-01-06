#!/usr/bin/env python3
"""
This script tries to output information that can be used to derive a fuel price estimation model
based on item prices.

To achieve this, it tries to find for each station a day that satisfies the following constraints:
    * It is in the validity period of the vendor iventories we have stored for that station
    * We have a complete set of prices for all items sold from vendors for that day
    * We have at least one fuel price reading for the station
This script takes the most recent day which satisfies these constraints, and produces in the output:
    * station
    * day
    * fuel price per gram (median of all readings)
    * per vendor, the prices (only credit prices) for all items (by slug)

"""
import sys
import pytz
import numpy as np
import json
from datetime import date

from collections import defaultdict
from utt.model import (
    FuelPriceReading,
    VendorInventory,
    VendorItemPriceReading,
)
from utt import app

def min_dt(dts):
    current = dts.pop(0)
    for item in dts:
        if item < current:
            current = item
    return current
def max_dt(dts):
    current = dts.pop(0)
    for item in dts:
        if item > current:
            current = item
    return current

tz = pytz.timezone('Europe/Paris')


with app.app_context():
    debug = 1
    inventories = VendorInventory.query.filter_by(is_current=True)
    by_station = defaultdict(list)
    for iv in inventories:
        by_station[iv.vendor.station].append(iv)

    records = []

    for station, ivs in by_station.items():
        station_data = {
            'station': {
                'name': station.name,
                'system': station.system.name,
                'short': station.short,
            }
        }
        first_date = max_dt([iv.first_seen for iv in ivs])
        
        fuel_price_readings = FuelPriceReading.query.filter(
            FuelPriceReading.station_id == station.id,
            FuelPriceReading.when >= first_date,
        ).order_by(FuelPriceReading.when.desc())
        if debug:
            station_data['debug'] = {
                'start_date': str(first_date),
                'fuel_price_readings_count': fuel_price_readings.count(),
                'by_day': {}
            }

        # check for which days we have fuel price readings
        fpr_by_date = defaultdict(list)
        for f in fuel_price_readings:
            dt = f.when.astimezone(tz)
            day = date(dt.year, dt.month, dt.day)
            fpr_by_date[day].append(f)
        # check for which of he days we have price readings for *all* items from vendors
        for day in sorted(fpr_by_date.keys(), reverse=True):
            station_data['debug']['by_day'][str(day)] = {}
            has_full_prices = True
            for iv in ivs:
                item_ids = [ii.item_id for ii in iv.inventory_items]
                qry = VendorItemPriceReading.query.filter(
                    VendorItemPriceReading.item_id.in_(item_ids),
                    VendorItemPriceReading.vendor_inventory_id == iv.id,
                    VendorItemPriceReading.day == day,
                )
                if qry.count() != len(item_ids):
                    station_data['debug']['by_day'][str(day)][iv.vendor.name] = 'incomplete price readings'
                    has_full_prices = False
                    break
            if has_full_prices:
                price_per_g = np.median([fpr.price_per_g for fpr in fpr_by_date[day]])
                station_data['fuel_price_per_g'] = price_per_g;
                station_data['inventory_timestamp'] = str(first_date)
                station_data['day'] = str(day)
                station_data['vendors'] = {}
                for iv in ivs:
                    item_ids = [ii.item_id for ii in iv.inventory_items]
                    qry = VendorItemPriceReading.query.filter(
                        VendorItemPriceReading.item_id.in_(item_ids),
                        VendorItemPriceReading.vendor_inventory_id == iv.id,
                        VendorItemPriceReading.day == day,
                    )
                    prices = {vipr.item.slug: vipr.price_credits for vipr in qry.all() if vipr.price_credits is not None}
                    station_data['vendors'][iv.vendor.name] = prices
                        
                break
        
        if 'vendors' not in station_data:
            station_data['missing_data'] = True;
        records.append(station_data)
    json.dump(records, sys.stdout, indent=4, sort_keys=True)
