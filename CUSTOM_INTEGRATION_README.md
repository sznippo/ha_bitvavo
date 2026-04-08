# Bitvavo Custom Integration (native Home Assistant entities)

This integration creates native Home Assistant sensors (no MQTT required).

## Features

- Market sensors per configured market:
  - Last price
  - 24h change (%)
  - 24h volume (base)
  - 24h volume quote (quote currency)
- Optional private sensors when API key/secret are configured:
  - Asset balances (available / in order)
  - Fee sensors (maker fee, taker fee, tier)

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
