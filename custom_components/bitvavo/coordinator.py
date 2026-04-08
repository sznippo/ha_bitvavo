from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_MARKETS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MARKETS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


@dataclass
class BitvavoData:
    markets: dict[str, dict[str, Any]]
    balances: list[dict[str, Any]]
    fees: dict[str, Any]


class BitvavoApiClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str | None, api_secret: str | None) -> None:
        self._session = session
        self._api_key = api_key or ""
        self._api_secret = api_secret or ""

    def _signature(self, timestamp_ms: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp_ms}{method}{path}{body}".encode("utf-8")
        secret = self._api_secret.encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    @property
    def has_private_auth(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def _request_public(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        async with self._session.get(url, params=params or {}, timeout=REQUEST_TIMEOUT) as response:
            response.raise_for_status()
            return await response.json()

    async def _request_private(self, method: str, path: str, body_obj: dict[str, Any] | None = None) -> Any:
        if not self._api_key or not self._api_secret:
            raise UpdateFailed("Private endpoint requires api_key/api_secret")

        body_obj = body_obj or {}
        body = json.dumps(body_obj, separators=(",", ":")) if body_obj else ""
        timestamp_ms = str(int(time.time() * 1000))

        headers = {
            "Bitvavo-Access-Key": self._api_key,
            "Bitvavo-Access-Timestamp": timestamp_ms,
            "Bitvavo-Access-Signature": self._signature(timestamp_ms, method, path, body),
            "Content-Type": "application/json",
        }

        url = f"{BASE_URL}{path}"
        async with self._session.request(
            method=method,
            url=url,
            headers=headers,
            data=body,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def async_get_ticker_24h(self, market: str) -> dict[str, Any]:
        payload = await self._request_public("/ticker/24h", params={"market": market})
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            return payload
        return {}

    async def async_get_balances(self) -> list[dict[str, Any]]:
        payload = await self._request_private("GET", "/account")
        return payload if isinstance(payload, list) else []

    async def async_get_fees(self) -> dict[str, Any]:
        payload = await self._request_private("GET", "/account/fees")
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            return payload
        return {}


class BitvavoDataUpdateCoordinator(DataUpdateCoordinator[BitvavoData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.markets = [
            m.strip().upper()
            for m in entry.options.get(CONF_MARKETS, entry.data.get(CONF_MARKETS, DEFAULT_MARKETS)).split(",")
            if m.strip()
        ]

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        session = async_get_clientsession(hass)
        self.api = BitvavoApiClient(
            session=session,
            api_key=entry.options.get(CONF_API_KEY, entry.data.get(CONF_API_KEY)),
            api_secret=entry.options.get(CONF_API_SECRET, entry.data.get(CONF_API_SECRET)),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

    async def _async_update_data(self) -> BitvavoData:
        markets_data: dict[str, dict[str, Any]] = {}

        try:
            for market in self.markets:
                markets_data[market] = await self.api.async_get_ticker_24h(market)
        except Exception as err:
            raise UpdateFailed(f"Failed loading market data: {err}") from err

        balances: list[dict[str, Any]] = []
        fees: dict[str, Any] = {}

        if self.api.has_private_auth:
            try:
                balances = await self.api.async_get_balances()
                fees = await self.api.async_get_fees()
            except Exception as err:
                _LOGGER.warning("Private data not available: %s", err)

        return BitvavoData(markets=markets_data, balances=balances, fees=fees)
