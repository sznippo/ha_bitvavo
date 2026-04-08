from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_MARKETS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MARKETS,
    DEFAULT_SCAN_INTERVAL,
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
