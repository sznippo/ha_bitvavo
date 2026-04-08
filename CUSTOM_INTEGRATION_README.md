# Bitvavo Custom Integration (native Home Assistant entities)

This integration creates native Home Assistant sensors (no MQTT required).

## Features

- Market sensors per configured market:
  - Last price
  - 24h change (%)
  - 24h volume (base)
  - 24h volume quote (quote currency)
  - 24h high/low
  - VWAP
  - Bid/Ask
  - Spread and spread %
- Optional private sensors when API key/secret are configured:
  - Asset balances (available / in order)
  - Fee sensors (maker fee, taker fee, tier)
- Portfolio EUR sensors:
  - Available portfolio EUR
  - Total portfolio EUR
- Health/diagnostic sensors:
  - Data mode
  - Last successful update
  - API error count
  - Last error

## Installation (manual)

1. Copy `custom_components/bitvavo` into your Home Assistant config directory under `custom_components/`.
2. Restart Home Assistant.
3. Open Settings -> Devices & Services -> Add Integration.
4. Search for `Bitvavo`.
5. Configure markets (for example `BTC-EUR,ETH-EUR`) and update interval.
6. Optionally set API key + secret to enable account/fee sensors.

## Notes

- Public market data works without API key.
- Private endpoints require key and secret with read permission.
- 24h change is calculated as `(last - open) / open * 100`.
- The integration uses Home Assistant runtime dependencies (`aiohttp`, `voluptuous`), so you do not need to install packages on the host OS.
- You can add new markets later via: Settings -> Devices & Services -> Bitvavo -> Configure.
- Changing markets triggers an automatic integration reload, and sensors for new markets are created.
- In options you can enable/disable sensor groups (market, balance, fee, health, portfolio).
- Soft cleanup can disable removed market sensors instead of deleting them.

## Services

- `bitvavo.refresh_data`
  - Triggers immediate refresh for one entry (`entry_id`) or all entries.
- `bitvavo.set_markets`
  - Updates `markets` at runtime for one entry (`entry_id`) or all entries and reloads automatically.
