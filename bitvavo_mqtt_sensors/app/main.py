import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
import requests

BASE_URL = "https://api.bitvavo.com/v2"
ACCESS_WINDOW_MS = "10000"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger("bitvavo-addon")


@dataclass
class Config:
    api_key: str
    api_secret: str
    operator_id: str
    markets: list[str]
    poll_interval: int
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_topic_prefix: str
    mqtt_tls: bool


class BitvavoClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()

    def _signature(self, timestamp_ms: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp_ms}{method}{path}{body}".encode("utf-8")
        secret = self.api_secret.encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    def _request_private(self, method: str, path: str, body_obj: dict[str, Any] | None = None) -> Any:
        body_obj = body_obj or {}
        body = json.dumps(body_obj, separators=(",", ":")) if body_obj else ""
        timestamp_ms = str(int(time.time() * 1000))
        headers = {
            "Bitvavo-Access-Key": self.api_key,
            "Bitvavo-Access-Timestamp": timestamp_ms,
            "Bitvavo-Access-Signature": self._signature(timestamp_ms, method, f"/v2{path}", body),
            "Bitvavo-Access-Window": ACCESS_WINDOW_MS,
            "Content-Type": "application/json",
        }

        url = f"{BASE_URL}{path}"
        response = self.session.request(method=method, url=url, headers=headers, data=body, timeout=15)
        response.raise_for_status()
        return response.json()

    def _request_public(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        response = self.session.get(url, params=params or {}, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_balances(self) -> list[dict[str, Any]]:
        data = self._request_private("GET", "/account")
        return data if isinstance(data, list) else []

    def get_fees(self) -> dict[str, Any]:
        data = self._request_private("GET", "/account/fees")
        if isinstance(data, list):
            return data[0] if data else {}
        if isinstance(data, dict):
            return data
        return {}

    def get_ticker_price(self, market: str) -> dict[str, Any]:
        data = self._request_public("/ticker/price", params={"market": market})
        if isinstance(data, list):
            return data[0] if data else {}
        if isinstance(data, dict):
            return data
        return {}


class MqttPublisher:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bitvavo-ha-addon")
        if cfg.mqtt_username:
            self.client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password or None)
        if cfg.mqtt_tls:
            self.client.tls_set()

    @staticmethod
    def _sanitize(value: str) -> str:
        return value.lower().replace("-", "_").replace(" ", "_")

    def connect(self) -> None:
        LOG.info("Connecting MQTT %s:%s", self.cfg.mqtt_host, self.cfg.mqtt_port)
        self.client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=60)
        self.client.loop_start()

    def publish_discovery(self, sensor_id: str, name: str, state_topic: str, unit: str | None = None) -> None:
        discovery_topic = f"homeassistant/sensor/bitvavo_{sensor_id}/config"
        payload = {
            "name": name,
            "unique_id": f"bitvavo_{sensor_id}",
            "state_topic": state_topic,
            "device": {
                "identifiers": ["bitvavo_addon"],
                "name": "Bitvavo",
                "manufacturer": "Bitvavo",
                "model": "MQTT Add-on",
            },
        }
        if unit:
            payload["unit_of_measurement"] = unit

        self.client.publish(discovery_topic, json.dumps(payload), qos=1, retain=True)

    def publish_state(self, topic: str, value: Any) -> None:
        self.client.publish(topic, str(value), qos=1, retain=True)

    def publish_balance(self, symbol: str, available: Any, in_order: Any) -> None:
        sid = self._sanitize(symbol)

        available_topic = f"{self.cfg.mqtt_topic_prefix}/balance/{sid}/available"
        in_order_topic = f"{self.cfg.mqtt_topic_prefix}/balance/{sid}/in_order"

        self.publish_discovery(
            sensor_id=f"balance_{sid}_available",
            name=f"Bitvavo {symbol} Available",
            state_topic=available_topic,
            unit=symbol,
        )
        self.publish_discovery(
            sensor_id=f"balance_{sid}_in_order",
            name=f"Bitvavo {symbol} In Order",
            state_topic=in_order_topic,
            unit=symbol,
        )

        self.publish_state(available_topic, available)
        self.publish_state(in_order_topic, in_order)

    def publish_fee(self, key: str, value: Any) -> None:
        sid = self._sanitize(key)
        topic = f"{self.cfg.mqtt_topic_prefix}/fees/{sid}"
        self.publish_discovery(
            sensor_id=f"fees_{sid}",
            name=f"Bitvavo Fee {key}",
            state_topic=topic,
            unit="",
        )
        self.publish_state(topic, value)

    def publish_price(self, market: str, price: Any) -> None:
        sid = self._sanitize(market)
        topic = f"{self.cfg.mqtt_topic_prefix}/price/{sid}"
        self.publish_discovery(
            sensor_id=f"price_{sid}",
            name=f"Bitvavo {market} Price",
            state_topic=topic,
            unit="EUR" if market.endswith("-EUR") else None,
        )
        self.publish_state(topic, price)


def load_config() -> Config:
    markets_raw = os.getenv("BITVAVO_MARKETS", "BTC-EUR,ETH-EUR")
    markets = [m.strip().upper() for m in markets_raw.split(",") if m.strip()]

    cfg = Config(
        api_key=os.getenv("BITVAVO_API_KEY", ""),
        api_secret=os.getenv("BITVAVO_API_SECRET", ""),
        operator_id=os.getenv("BITVAVO_OPERATOR_ID", ""),
        markets=markets,
        poll_interval=int(os.getenv("POLL_INTERVAL", "30")),
        mqtt_host=os.getenv("MQTT_HOST", "core-mosquitto"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        mqtt_username=os.getenv("MQTT_USERNAME", ""),
        mqtt_password=os.getenv("MQTT_PASSWORD", ""),
        mqtt_topic_prefix=os.getenv("MQTT_TOPIC_PREFIX", "bitvavo"),
        mqtt_tls=os.getenv("MQTT_TLS", "false").lower() == "true",
    )

    if not cfg.api_key or not cfg.api_secret:
        raise RuntimeError("BITVAVO_API_KEY and BITVAVO_API_SECRET are required")

    return cfg


def run() -> None:
    cfg = load_config()
    bitvavo = BitvavoClient(cfg.api_key, cfg.api_secret)
    publisher = MqttPublisher(cfg)
    publisher.connect()

    LOG.info("Addon started with %d market(s), interval=%ss", len(cfg.markets), cfg.poll_interval)

    while True:
        try:
            balances = bitvavo.get_balances()
            for row in balances:
                symbol = str(row.get("symbol", "")).upper()
                if not symbol:
                    continue
                publisher.publish_balance(
                    symbol=symbol,
                    available=row.get("available", "0"),
                    in_order=row.get("inOrder", "0"),
                )

            fees = bitvavo.get_fees()
            for key in ("makeFee", "takeFee", "tier"):
                if key in fees:
                    publisher.publish_fee(key, fees[key])

            for market in cfg.markets:
                ticker = bitvavo.get_ticker_price(market)
                price = ticker.get("price")
                if price is not None:
                    publisher.publish_price(market, price)

            LOG.info("Published balances, fees, and prices")
        except Exception as exc:
            LOG.exception("Polling cycle failed: %s", exc)

        time.sleep(cfg.poll_interval)


if __name__ == "__main__":
    run()
