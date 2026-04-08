# Bitvavo Home Assistant Integration

Native Home Assistant custom integration for Bitvavo market and account sensors.

## HACS Installation

1. Open HACS -> Integrations -> Custom repositories.
2. Add your repository URL.
3. Category: Integration.
4. Search for `Bitvavo` in HACS and install.
5. Restart Home Assistant.
6. Go to Settings -> Devices & Services -> Add Integration -> `Bitvavo`.

## Features

- Market sensors per configured market:
  - Last price
  - 24h change (%)
  - 24h volume
  - 24h quote volume
  - 24h high/low
  - VWAP
  - Bid/Ask
  - Spread and Spread %
- Optional private account sensors with API credentials:
  - Balances (available, in order)
  - Fees (maker, taker, tier)
- Portfolio sensors:
  - Total portfolio value in EUR
  - Available portfolio value in EUR
- Health/diagnostic sensors:
  - Data mode (full/public-only)
  - Last successful update
  - API error count
  - Last error message
- Runtime services:
  - `bitvavo.refresh_data`
  - `bitvavo.set_markets`
- Reliability:
  - Retry with exponential backoff + jitter for transient API failures

## Repository Structure

- `custom_components/bitvavo` -> HACS/Home Assistant integration code
- `bitvavo_mqtt_sensors` -> Optional standalone Home Assistant add-on (MQTT based)

## Notes

- For HACS, only `custom_components/bitvavo` is used.
- API key/secret are optional. Without them, public market sensors still work.
