#!/usr/bin/with-contenv bashio
set -euo pipefail

export BITVAVO_API_KEY="$(bashio::config 'bitvavo_api_key')"
export BITVAVO_API_SECRET="$(bashio::config 'bitvavo_api_secret')"
export BITVAVO_OPERATOR_ID="$(bashio::config 'operator_id')"
export BITVAVO_MARKETS="$(bashio::config 'markets')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"

export MQTT_HOST="$(bashio::config 'mqtt_host')"
export MQTT_PORT="$(bashio::config 'mqtt_port')"
export MQTT_USERNAME="$(bashio::config 'mqtt_username')"
export MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
export MQTT_TOPIC_PREFIX="$(bashio::config 'mqtt_topic_prefix')"
export MQTT_TLS="$(bashio::config 'mqtt_tls')"

bashio::log.info "Starting Bitvavo MQTT Sensors addon"
exec python3 /app/main.py
