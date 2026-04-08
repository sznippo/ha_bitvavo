from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_CHANGE_24H_PRECISION,
    CONF_ENABLE_BALANCE_SENSORS,
    CONF_ENABLE_FEE_SENSORS,
    CONF_ENABLE_HEALTH_SENSORS,
    CONF_ENABLE_MARKET_SENSORS,
    CONF_ENABLE_PORTFOLIO_SENSORS,
    CONF_MARKETS,
    CONF_SCAN_INTERVAL,
    CONF_SOFT_CLEANUP,
    DEFAULT_ENABLE_BALANCE_SENSORS,
    DEFAULT_ENABLE_FEE_SENSORS,
    DEFAULT_ENABLE_HEALTH_SENSORS,
    DEFAULT_ENABLE_MARKET_SENSORS,
    DEFAULT_ENABLE_PORTFOLIO_SENSORS,
    DEFAULT_CHANGE_24H_PRECISION,
    DEFAULT_MARKETS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SOFT_CLEANUP,
    DOMAIN,
)


class BitvavoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            title = "Bitvavo"
            markets = user_input.get(CONF_MARKETS, DEFAULT_MARKETS)
            if markets:
                first_market = markets.split(",")[0].strip().upper()
                if first_market:
                    title = f"Bitvavo {first_market}"

            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_MARKETS, default=DEFAULT_MARKETS): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=10, max=3600),
                ),
                vol.Required(CONF_CHANGE_24H_PRECISION, default=DEFAULT_CHANGE_24H_PRECISION): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=0, max=8),
                ),
                vol.Required(CONF_SOFT_CLEANUP, default=DEFAULT_SOFT_CLEANUP): bool,
                vol.Required(CONF_ENABLE_MARKET_SENSORS, default=DEFAULT_ENABLE_MARKET_SENSORS): bool,
                vol.Required(CONF_ENABLE_BALANCE_SENSORS, default=DEFAULT_ENABLE_BALANCE_SENSORS): bool,
                vol.Required(CONF_ENABLE_FEE_SENSORS, default=DEFAULT_ENABLE_FEE_SENSORS): bool,
                vol.Required(CONF_ENABLE_HEALTH_SENSORS, default=DEFAULT_ENABLE_HEALTH_SENSORS): bool,
                vol.Required(CONF_ENABLE_PORTFOLIO_SENSORS, default=DEFAULT_ENABLE_PORTFOLIO_SENSORS): bool,
                vol.Optional(CONF_API_KEY, default=""): str,
                vol.Optional(CONF_API_SECRET, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return BitvavoOptionsFlowHandler(config_entry)


class BitvavoOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MARKETS,
                    default=self._config_entry.options.get(
                        CONF_MARKETS,
                        self._config_entry.data.get(CONF_MARKETS, DEFAULT_MARKETS),
                    ),
                ): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Required(
                    CONF_CHANGE_24H_PRECISION,
                    default=self._config_entry.options.get(
                        CONF_CHANGE_24H_PRECISION,
                        self._config_entry.data.get(CONF_CHANGE_24H_PRECISION, DEFAULT_CHANGE_24H_PRECISION),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
                vol.Required(
                    CONF_SOFT_CLEANUP,
                    default=self._config_entry.options.get(
                        CONF_SOFT_CLEANUP,
                        self._config_entry.data.get(CONF_SOFT_CLEANUP, DEFAULT_SOFT_CLEANUP),
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_MARKET_SENSORS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_MARKET_SENSORS,
                        self._config_entry.data.get(CONF_ENABLE_MARKET_SENSORS, DEFAULT_ENABLE_MARKET_SENSORS),
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_BALANCE_SENSORS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_BALANCE_SENSORS,
                        self._config_entry.data.get(CONF_ENABLE_BALANCE_SENSORS, DEFAULT_ENABLE_BALANCE_SENSORS),
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_FEE_SENSORS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_FEE_SENSORS,
                        self._config_entry.data.get(CONF_ENABLE_FEE_SENSORS, DEFAULT_ENABLE_FEE_SENSORS),
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_HEALTH_SENSORS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_HEALTH_SENSORS,
                        self._config_entry.data.get(CONF_ENABLE_HEALTH_SENSORS, DEFAULT_ENABLE_HEALTH_SENSORS),
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_PORTFOLIO_SENSORS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_PORTFOLIO_SENSORS,
                        self._config_entry.data.get(CONF_ENABLE_PORTFOLIO_SENSORS, DEFAULT_ENABLE_PORTFOLIO_SENSORS),
                    ),
                ): bool,
                vol.Optional(
                    CONF_API_KEY,
                    default=self._config_entry.options.get(
                        CONF_API_KEY,
                        self._config_entry.data.get(CONF_API_KEY, ""),
                    ),
                ): str,
                vol.Optional(
                    CONF_API_SECRET,
                    default=self._config_entry.options.get(
                        CONF_API_SECRET,
                        self._config_entry.data.get(CONF_API_SECRET, ""),
                    ),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
