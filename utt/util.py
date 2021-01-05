import pytz
from datetime import datetime, date

tau_tz = pytz.timezone('Europe/Paris')

def today_datetime():
    n = datetime.now(tau_tz)
    return n.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)

def today():
    dt = datetime.now(tau_tz)
    return date(dt.year, dt.month, dt.day)
