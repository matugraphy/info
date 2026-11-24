"""Wait for tomorrow's Elering prices when a run starts before they are out.

GitHub starts scheduled runs only every few hours, whatever the cron says, so a morning run used to leave
tomorrow's prices missing until the next run, often in the evening. Elering publishes them around 14:00
Tallinn time. A run that starts between 06:00 and 15:59 Tallinn time with tomorrow still missing checks every
10 minutes until the prices appear, for at most 5 h 30 min, and then the normal fetch and publish follow.
Runner minutes are free for a public repository. This step never fails the job.
"""
import datetime as d
import json
import time
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Tallinn")
UA = "matugraphy-info/1.0 https://github.com/matugraphy/info"
START_HOURS = range(6, 16)
CHECK_EVERY = 10 * 60
MAX_WAIT = 5.5 * 3600


def tomorrow_prices():
    day = d.datetime.now(TZ).date() + d.timedelta(days=1)
    start = d.datetime.combine(day, d.time(), TZ).astimezone(d.timezone.utc)
    end = start + d.timedelta(days=1, milliseconds=-1)
    url = ("https://dashboard.elering.ee/api/nps/price?start=" + start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
           + "&end=" + end.strftime("%Y-%m-%dT%H:%M:%S.999Z"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return len(json.load(urllib.request.urlopen(req, timeout=60))["data"]["ee"])


def have_tomorrow():
    try:
        return tomorrow_prices() >= 92  # 96 quarter hours; 92 or 100 on a clock-change day
    except Exception as e:
        print(f"::warning::Elering check failed: {e}")
        return False


if d.datetime.now(TZ).hour not in START_HOURS:
    print("Outside the waiting window; not waiting.")
elif have_tomorrow():
    print("Tomorrow's prices are already out.")
else:
    began = time.time()
    while time.time() - began < MAX_WAIT:
        time.sleep(CHECK_EVERY)
        if have_tomorrow():
            print(f"Tomorrow's prices appeared after {round((time.time() - began) / 60)} minutes.")
            break
    else:
        print("::warning::Tomorrow's prices did not appear in time; publishing what there is.")
