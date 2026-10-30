# Elekter ja ilm

A one-page home-screen display: a dark clock home screen, the Estonian day-ahead electricity price (Elering / Nord Pool) and the Yr forecast for Mäe-Rõuge (MET Norway).

- `index.html` is the whole page. It reads `prices.json` and `weather.json` next to it.
- `scripts/fetch.py` refreshes both data files.
- `.github/workflows/update.yml` runs the fetch every hour, commits new data and publishes the site to GitHub Pages.

Forecast data: Yr / MET Norway, CC BY 4.0. Price data: Elering.
