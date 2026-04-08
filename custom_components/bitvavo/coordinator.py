from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import random
import time
from decimal import Decimal, InvalidOperation
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
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.6
ACCESS_WINDOW_MS = "10000"


@dataclass
class BitvavoData:
    markets: dict[str, dict[str, Any]]
    balances: list[dict[str, Any]]
    fees: dict[str, Any]
    portfolio: dict[str, Decimal]
    last_success_at: datetime | None
    last_error: str | None
    error_count: int
    data_mode: str


class BitvavoApiClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str | None, api_secret: str | None) -> None:
        self._session = session
        self._api_key = (api_key or "").strip()
        self._api_secret = (api_secret or "").strip()

    def _signature(self, timestamp_ms: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp_ms}{method}{path}{body}".encode("utf-8")
        secret = self._api_secret.encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    @property
    def has_private_auth(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def _request_json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body_obj: dict[str, Any] | None = None,
        private: bool = False,
    ) -> Any:
        body_obj = body_obj or {}
        body = json.dumps(body_obj, separators=(",", ":")) if body_obj else ""

        last_error: Exception | None = None
        url = f"{BASE_URL}{path}"

        for attempt in range(1, MAX_RETRIES + 1):
            headers = {"Content-Type": "application/json"}
            if private:
                if not self._api_key or not self._api_secret:
                    raise UpdateFailed("Private endpoint requires api_key/api_secret")

            signature_paths = [f"/v2{path}"] if private else [""]
            if private:
                signature_paths.append(path)

            try:
                for idx, signature_path in enumerate(signature_paths):
                    request_headers = dict(headers)
                    if private:
                        timestamp_ms = str(int(time.time() * 1000))
                        request_headers.update(
                            {
                                "Bitvavo-Access-Key": self._api_key,
                                "Bitvavo-Access-Timestamp": timestamp_ms,
                                "Bitvavo-Access-Signature": self._signature(timestamp_ms, method, signature_path, body),
                                "Bitvavo-Access-Window": ACCESS_WINDOW_MS,
                            }
                        )

                    async with self._session.request(
                        method=method,
                        url=url,
                        params=params or {},
                        headers=request_headers,
                        data=body,
                        timeout=REQUEST_TIMEOUT,
                    ) as response:
                        if response.status == 403 and private and idx == 0:
                            # Fallback for environments where path-only signature is expected.
                            continue

                        if response.status in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                            await asyncio.sleep(self._retry_delay(attempt))
                            break

                        if response.status >= 400:
                            error_text = await response.text()
                            raise UpdateFailed(f"Request failed for {path}: {response.status} {error_text}")

                        return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_error = err
                if attempt >= MAX_RETRIES:
                    break
                await asyncio.sleep(self._retry_delay(attempt))
            except UpdateFailed as err:
                last_error = err
                if attempt >= MAX_RETRIES:
                    break
                await asyncio.sleep(self._retry_delay(attempt))

        if last_error is not None:
            raise UpdateFailed(f"Request failed for {path}: {last_error}") from last_error
        raise UpdateFailed(f"Request failed for {path}")

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        # Exponential backoff with jitter to spread retries.
        base = BASE_RETRY_DELAY * (2 ** (attempt - 1))
        return base + random.uniform(0.0, 0.25)

    async def _request_public(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request_json("GET", path, params=params, private=False)

    async def _request_private(self, method: str, path: str, body_obj: dict[str, Any] | None = None) -> Any:
        if not self._api_key or not self._api_secret:
            raise UpdateFailed("Private endpoint requires api_key/api_secret")
        return await self._request_json(method, path, body_obj=body_obj, private=True)

    async def async_get_ticker_24h(self, market: str) -> dict[str, Any]:
        payload = await self._request_public("/ticker/24h", params={"market": market})
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            return payload
        return {}

    async def async_get_ticker_book(self, market: str) -> dict[str, Any]:
        payload = await self._request_public("/ticker/book", params={"market": market})
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            return payload
        return {}

    async def async_get_all_prices(self) -> dict[str, Decimal]:
        payload = await self._request_public("/ticker/price")
        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            rows = [payload]

        prices: dict[str, Decimal] = {}
        for row in rows:
            market = str(row.get("market", "")).upper()
            price = row.get("price")
            if not market or price is None:
                continue
            try:
                prices[market] = Decimal(str(price))
            except (InvalidOperation, TypeError):
                continue
        return prices

    async def async_get_balances(self) -> list[dict[str, Any]]:
        payload = await self._request_private("GET", "/balance")
        return payload if isinstance(payload, list) else []

    async def async_get_fees(self) -> dict[str, Any]:
        payload = await self._request_private("GET", "/account")
        return self._normalize_fees(payload)

    @staticmethod
    def _normalize_fees(payload: Any) -> dict[str, Any]:
        # Bitvavo fee responses can differ by account type/API version.
        # Normalize to: makeFee, takeFee, tier
        candidate: dict[str, Any] = {}

        if isinstance(payload, dict):
            candidate = payload
        elif isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                if any(k in item for k in ("makeFee", "makerFee", "maker", "takeFee", "takerFee", "taker", "tier", "feeTier")):
                    candidate = item
                    break
            if not candidate and payload and isinstance(payload[0], dict):
                candidate = payload[0]

        if not candidate:
            return {}

        normalized: dict[str, Any] = {}

        if "makeFee" in candidate:
            normalized["makeFee"] = candidate["makeFee"]
        elif "makerFee" in candidate:
            normalized["makeFee"] = candidate["makerFee"]
        elif "maker" in candidate:
            normalized["makeFee"] = candidate["maker"]

        if "takeFee" in candidate:
            normalized["takeFee"] = candidate["takeFee"]
        elif "takerFee" in candidate:
            normalized["takeFee"] = candidate["takerFee"]
        elif "taker" in candidate:
            normalized["takeFee"] = candidate["taker"]

        if "tier" in candidate:
            normalized["tier"] = candidate["tier"]
        elif "feeTier" in candidate:
            normalized["tier"] = candidate["feeTier"]

        return normalized


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
        self._error_count = 0
        self._last_error: str | None = None
        self._last_success_at: datetime | None = None

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
                ticker_24h = await self.api.async_get_ticker_24h(market)
                book = await self.api.async_get_ticker_book(market)

                merged = dict(ticker_24h)
                if "bid" in book:
                    merged["bid"] = book["bid"]
                if "ask" in book:
                    merged["ask"] = book["ask"]

                try:
                    bid = Decimal(str(merged.get("bid")))
                    ask = Decimal(str(merged.get("ask")))
                    if bid > 0 and ask > 0 and ask >= bid:
                        spread = ask - bid
                        merged["spread"] = str(spread)
                        merged["spread_pct"] = str((spread / ask) * Decimal("100"))
                except (InvalidOperation, TypeError):
                    pass

                markets_data[market] = merged
        except Exception as err:
            self._error_count += 1
            self._last_error = str(err)
            raise UpdateFailed(f"Failed loading market data: {err}") from err

        balances: list[dict[str, Any]] = []
        fees: dict[str, Any] = {}
        portfolio: dict[str, Decimal] = {
            "available_eur": Decimal("0"),
            "total_eur": Decimal("0"),
        }
        data_mode = "public_only"

        if self.api.has_private_auth:
            try:
                balances = await self.api.async_get_balances()
                fees = await self.api.async_get_fees()
                prices = await self.api.async_get_all_prices()
                portfolio = self._compute_portfolio_eur(balances, prices)
                data_mode = "full_data"
            except Exception as err:
                _LOGGER.warning("Private data not available: %s", err)
                self._last_error = str(err)
                data_mode = "public_only_private_error"

        self._last_success_at = datetime.now(timezone.utc)
        if data_mode == "full_data" or self._last_error is None:
            self._last_error = None

        return BitvavoData(
            markets=markets_data,
            balances=balances,
            fees=fees,
            portfolio=portfolio,
            last_success_at=self._last_success_at,
            last_error=self._last_error,
            error_count=self._error_count,
            data_mode=data_mode,
        )

    @staticmethod
    def _compute_portfolio_eur(
        balances: list[dict[str, Any]],
        prices: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        available_total = Decimal("0")
        total = Decimal("0")

        for row in balances:
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue

            try:
                available = Decimal(str(row.get("available", "0")))
            except (InvalidOperation, TypeError):
                available = Decimal("0")

            try:
                in_order = Decimal(str(row.get("inOrder", "0")))
            except (InvalidOperation, TypeError):
                in_order = Decimal("0")

            balance_total = available + in_order

            if symbol == "EUR":
                price_eur = Decimal("1")
            else:
                price_eur = prices.get(f"{symbol}-EUR")
                if price_eur is None:
                    continue

            available_total += available * price_eur
            total += balance_total * price_eur

        return {
            "available_eur": available_total,
            "total_eur": total,
        }
