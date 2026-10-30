"""Fetch the Estonian day-ahead electricity price (Elering) and the Mäe-Rõuge forecast (MET Norway / Yr) into prices.json and weather.json."""
import datetime as d
import json
import urllib.request

UA = "matugraphy-info/1.0 https://github.com/matugraphy/info"
now = d.datetime.now(d.timezone.utc)


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60))


# Elering: yesterday 00:00 UTC to the end of the day after tomorrow, 15-minute prices in EUR/MWh.
s = (now - d.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
e = (now + d.timedelta(days=2)).strftime("%Y-%m-%dT23:59:59.999Z")
ee = [[p["timestamp"], p["price"]] for p in get(f"https://dashboard.elering.ee/api/nps/price?start={s}&end={e}")["data"]["ee"]]
assert len(ee) > 90, "too few prices"
json.dump({"fetched": int(now.timestamp()), "ee": ee}, open("prices.json", "w"))

# MET Norway: hourly steps with the 1-hour and 6-hour summaries the page shows.
j = get("https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=57.7328&lon=26.9286&altitude=142")
out = []
for t in j["properties"]["timeseries"]:
    i = t["data"]["instant"]["details"]
    n1 = t["data"].get("next_1_hours")
    n6 = t["data"].get("next_6_hours")
    ts = int(d.datetime.fromisoformat(t["time"].replace("Z", "+00:00")).timestamp())
    out.append([ts, i.get("air_temperature"), i.get("wind_speed"), i.get("wind_speed_of_gust"), i.get("wind_from_direction"),
                n1 and n1["summary"]["symbol_code"], n1 and n1["details"].get("precipitation_amount"),
                n6 and n6["summary"]["symbol_code"], n6 and n6["details"].get("precipitation_amount_min"), n6 and n6["details"].get("precipitation_amount_max")])
assert len(out) > 40, "too few forecast steps"
json.dump({"fetched": int(now.timestamp()), "updated": j["properties"]["meta"]["updated_at"], "ts": out}, open("weather.json", "w"))
print(len(ee), "prices,", len(out), "forecast steps")
