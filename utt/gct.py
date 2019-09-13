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

def as_gct(dt):
    delta = dt - catastrophe
    total_units = str(int(delta.total_seconds() / 0.864 + 0.5))
    return total_units[:-7] + '.' + total_units[-7:-5] \
                           + '/' + total_units[-5:-3] \
                           + ':' + total_units[-3:]
