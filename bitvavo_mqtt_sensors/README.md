# Bitvavo MQTT Sensors Add-on

This Home Assistant add-on polls Bitvavo and publishes values as MQTT sensors.

## Published sensors

- Account balances: available and in-order amount per asset
- Fee settings: maker fee, taker fee, tier
- Market prices for configured symbols (for example `BTC-EUR`)

## Requirements

- Home Assistant with MQTT broker integration
- Bitvavo API key + secret with read access

## Install as local add-on

1. Place this repository in your Home Assistant add-on directory.
2. Open Home Assistant -> Settings -> Add-ons -> Add-on Store.
3. Click menu -> Repositories, add your local repository path if needed.
4. Open `Bitvavo MQTT Sensors`, set options, and start it.

## Add-on options

- `bitvavo_api_key`: Bitvavo API key
- `bitvavo_api_secret`: Bitvavo API secret
- `markets`: Comma-separated markets, e.g. `BTC-EUR,ETH-EUR`
- `poll_interval`: Seconds between API polls (10..3600)
- `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`
- `mqtt_topic_prefix`: Prefix for state topics
- `mqtt_tls`: Set `true` for TLS

## Notes

- MQTT discovery messages are retained.
- Fee response from Bitvavo can be object or array; both are handled.
- If a market or endpoint fails temporarily, the add-on logs and retries on the next cycle.
- Python dependencies are bundled into the add-on image at build time (wheelhouse).
- No manual dependency installation on the Home Assistant host system is required.
