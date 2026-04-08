from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BitvavoDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class BitvavoMarketSensorDescription(SensorEntityDescription):
    value_key: str


MARKET_SENSORS: tuple[BitvavoMarketSensorDescription, ...] = (
    BitvavoMarketSensorDescription(
        key="last",
        name="Last Price",
        value_key="last",
        suggested_display_precision=2,
    ),
    BitvavoMarketSensorDescription(
        key="change_24h",
        name="24h Change",
        value_key="change_24h",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    BitvavoMarketSensorDescription(
        key="volume",
        name="24h Volume",
        value_key="volume",
        suggested_display_precision=6,
    ),
    BitvavoMarketSensorDescription(
        key="volume_quote",
        name="24h Volume Quote",
        value_key="volumeQuote",
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BitvavoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    for market in coordinator.markets:
        quote_symbol = market.split("-")[1] if "-" in market else None
        base_symbol = market.split("-")[0] if "-" in market else None

        for desc in MARKET_SENSORS:
            unit = None
            if desc.key == "last" and quote_symbol:
                unit = quote_symbol
            elif desc.key == "volume" and base_symbol:
                unit = base_symbol
            elif desc.key == "volume_quote" and quote_symbol:
                unit = quote_symbol

            entities.append(
                BitvavoMarketSensor(
                    coordinator=coordinator,
                    entry_id=entry.entry_id,
                    market=market,
                    description=desc,
                    native_unit=unit,
                )
            )

    balances = coordinator.data.balances if coordinator.data else []
    for row in balances:
        symbol = str(row.get("symbol", "")).upper()
        if not symbol:
            continue
        entities.append(BitvavoBalanceSensor(coordinator, entry.entry_id, symbol, "available"))
        entities.append(BitvavoBalanceSensor(coordinator, entry.entry_id, symbol, "inOrder"))

    for fee_key in ("makeFee", "takeFee", "tier"):
        entities.append(BitvavoFeeSensor(coordinator, entry.entry_id, fee_key))

    async_add_entities(entities)


class BitvavoBaseEntity(CoordinatorEntity[BitvavoDataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Bitvavo",
            manufacturer="Bitvavo",
            model="Trading API",
        )


class BitvavoMarketSensor(BitvavoBaseEntity):
    entity_description: BitvavoMarketSensorDescription

    def __init__(
        self,
        coordinator: BitvavoDataUpdateCoordinator,
        entry_id: str,
        market: str,
        description: BitvavoMarketSensorDescription,
        native_unit: str | None,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._market = market
        self._attr_unique_id = f"{entry_id}_{market}_{description.key}"
        self._attr_name = f"{market} {description.name}"
        self._attr_native_unit_of_measurement = native_unit
        if description.key in ("last", "volume", "volume_quote"):
            self._attr_state_class = "measurement"

    @property
    def available(self) -> bool:
        market_data = self.coordinator.data.markets.get(self._market, {})
        return bool(market_data)

    @property
    def native_value(self) -> Any:
        market_data = self.coordinator.data.markets.get(self._market, {})
        if not market_data:
            return None

        if self.entity_description.key == "change_24h":
            try:
                last = Decimal(str(market_data.get("last")))
                open_price = Decimal(str(market_data.get("open")))
                if open_price == 0:
                    return None
                return float((last - open_price) / open_price * Decimal(100))
            except (InvalidOperation, TypeError):
                return None

        value = market_data.get(self.entity_description.value_key)
        try:
            return float(value)
        except (TypeError, ValueError):
            return value


class BitvavoBalanceSensor(BitvavoBaseEntity):
    def __init__(
        self,
        coordinator: BitvavoDataUpdateCoordinator,
        entry_id: str,
        symbol: str,
        balance_key: str,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._symbol = symbol
        self._balance_key = balance_key
        pretty_key = "Available" if balance_key == "available" else "In Order"
        suffix = "available" if balance_key == "available" else "in_order"

        self._attr_unique_id = f"{entry_id}_{symbol}_{suffix}"
        self._attr_name = f"{symbol} {pretty_key}"
        self._attr_native_unit_of_measurement = symbol
        self._attr_state_class = "measurement"

    @property
    def native_value(self) -> Any:
        for row in self.coordinator.data.balances:
            if str(row.get("symbol", "")).upper() != self._symbol:
                continue
            value = row.get(self._balance_key)
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        return None

    @property
    def available(self) -> bool:
        return any(str(row.get("symbol", "")).upper() == self._symbol for row in self.coordinator.data.balances)


class BitvavoFeeSensor(BitvavoBaseEntity):
    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, entry_id: str, fee_key: str) -> None:
        super().__init__(coordinator, entry_id)
        self._fee_key = fee_key
        self._attr_unique_id = f"{entry_id}_{fee_key}"
        if fee_key == "makeFee":
            self._attr_name = "Maker Fee"
        elif fee_key == "takeFee":
            self._attr_name = "Taker Fee"
        elif fee_key == "tier":
            self._attr_name = "Fee Tier"
        else:
            self._attr_name = fee_key
        if fee_key in ("makeFee", "takeFee"):
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = "measurement"
            self._attr_suggested_display_precision = 3

    @property
    def native_value(self) -> Any:
        fees = self.coordinator.data.fees
        if self._fee_key not in fees:
            return None

        value = fees[self._fee_key]
        if self._fee_key in ("makeFee", "takeFee"):
            try:
                return float(value) * 100.0
            except (TypeError, ValueError):
                return None

        if self._fee_key == "tier":
            return str(value)

        return value

    @property
    def available(self) -> bool:
        return self._fee_key in self.coordinator.data.fees
