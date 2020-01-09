import re
from datetime import datetime, timedelta
import pytz

catastrophe = datetime(1964, 1, 22, 0, 0, 27, 689615, pytz.UTC)
gct_re = re.compile(r'([0-9]{3}\.[0-9]{2})/([0-9]{2}:[0-9]{3})(?:\s*GCT)?')

def parse_gct(in_):
    match = gct_re.match(in_)
    if match:
        days = int(match.group(1).replace('.', ''))
        seconds = int(match.group(2).replace(':', '')) * 0.864
        return catastrophe + timedelta(days=days, seconds=seconds)

def as_gct(dt, format=True):
    delta = dt - catastrophe
    total_units = str(int(delta.total_seconds() / 0.864 + 0.5))
    if not format:
        return total_units
    return total_units[:-7] + '.' + total_units[-7:-5] \
                           + '/' + total_units[-5:-3] \
                           + ':' + total_units[-3:]

def gct_duration(delta):
    if isinstance(delta, int):
        seconds = delta
    else:
        seconds = delta.total_seconds()
    units = int(seconds / 0.864)
    days = int(units / 100_000)
    units -= days * 100_000
    unit_str = '{:05d}'.format(units)
    unit_str = unit_str[0:2] + ':' + unit_str[2:]
    if days > 0:
        return 'D{:02d}/{}'.format(days, unit_str)
    else:
        return 'D/' + unit_str
