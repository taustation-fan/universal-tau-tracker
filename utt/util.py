import pytz
from datetime import datetime

def today_datetime():
    n = datetime.now(pytz.timezone('Europe/Paris'))
    return n.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
