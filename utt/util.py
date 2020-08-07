import pytz
from datetime import datetime, date

def today_datetime():
    n = datetime.now(pytz.timezone('Europe/Paris'))
    return n.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)

def today():
    dt = today_datetime()
    return date(dt.year, dt.month, dt.day)
