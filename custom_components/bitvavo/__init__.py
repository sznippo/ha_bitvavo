from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_MARKETS,
    CONF_SOFT_CLEANUP,
    DEFAULT_MARKETS,
    DEFAULT_SOFT_CLEANUP,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH_DATA,
    SERVICE_SET_MARKETS,
)
from .coordinator import BitvavoDataUpdateCoordinator

DATA_SERVICES_REGISTERED = "__services_registered__"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = BitvavoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await _async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not _entry_ids(hass):
            _async_unload_services(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: BitvavoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    old_markets = set(coordinator.markets)

    new_markets_raw = entry.options.get(CONF_MARKETS, entry.data.get(CONF_MARKETS, DEFAULT_MARKETS))
    new_markets = {m.strip().upper() for m in new_markets_raw.split(",") if m.strip()}

    removed_markets = old_markets - new_markets
    added_markets = new_markets - old_markets

    entity_registry = er.async_get(hass)
    entry_entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    soft_cleanup = bool(entry.options.get(CONF_SOFT_CLEANUP, entry.data.get(CONF_SOFT_CLEANUP, DEFAULT_SOFT_CLEANUP)))

    if removed_markets:
        for entity_entry in entry_entities:
            unique_id = entity_entry.unique_id or ""
            if not any(unique_id.startswith(f"{entry.entry_id}_{market}_") for market in removed_markets):
                continue

            if soft_cleanup:
                entity_registry.async_update_entity(
                    entity_entry.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )
            else:
                entity_registry.async_remove(entity_entry.entity_id)

    if soft_cleanup and added_markets:
        for entity_entry in entry_entities:
            unique_id = entity_entry.unique_id or ""
            if any(unique_id.startswith(f"{entry.entry_id}_{market}_") for market in added_markets):
                if entity_entry.disabled_by is not None:
                    entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(entry.entry_id)


def _entry_ids(hass: HomeAssistant) -> list[str]:
    return [key for key in hass.data.get(DOMAIN, {}).keys() if not key.startswith("__")]


async def _async_setup_services(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_SERVICES_REGISTERED):
        return

    async def _handle_refresh_data(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        target_ids = [entry_id] if entry_id else _entry_ids(hass)

        for target_id in target_ids:
            coordinator = hass.data.get(DOMAIN, {}).get(target_id)
            if coordinator is None:
                continue
            await coordinator.async_request_refresh()

    async def _handle_set_markets(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        markets = str(call.data.get("markets", ""))
        if not markets:
            return

        target_entries = []
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if entry_id and config_entry.entry_id != entry_id:
                continue
            target_entries.append(config_entry)

        for config_entry in target_entries:
            new_options = dict(config_entry.options)
            new_options[CONF_MARKETS] = markets
            hass.config_entries.async_update_entry(config_entry, options=new_options)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_DATA,
        _handle_refresh_data,
        schema=vol.Schema({vol.Optional("entry_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MARKETS,
        _handle_set_markets,
        schema=vol.Schema({vol.Required("markets"): str, vol.Optional("entry_id"): str}),
    )
    domain_data[DATA_SERVICES_REGISTERED] = True


def _async_unload_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA):
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH_DATA)
    if hass.services.has_service(DOMAIN, SERVICE_SET_MARKETS):
        hass.services.async_remove(DOMAIN, SERVICE_SET_MARKETS)
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DATA_SERVICES_REGISTERED] = False
