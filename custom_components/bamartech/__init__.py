"""Bamartech Home Assistant Integration.

On first load this integration:
  1. Serves ``bamartech-card.js`` from the bundled lovelace/static/ directory
     at the URL ``/bamartech_static/bamartech-card.js``.
  2. Calls ``add_extra_js_url`` so HA injects that URL as a
     ``<script type="module">`` in every frontend page load — this is the
     same mechanism used by HACS and browser_mod to make custom cards
     available without any manual resource configuration.
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import BamartechCoordinator

# ── Service schema ────────────────────────────────────────────────────────────
_VALID_COUNTERS = ["biopreparaty", "wywoz_osadow", "konserwacja"]

SET_COUNTER_SCHEMA = vol.Schema(
    {
        vol.Required("counter"): vol.In(_VALID_COUNTERS),
        vol.Required("index"):   vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
    }
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "switch", "binary_sensor"]

# URL at which the custom card JS will be served.
# The version query string busts the browser cache on every integration update.
_CARD_VERSION    = "1.0.0"
_STATIC_URL_PATH = "/bamartech_static"
_CARD_JS_URL     = f"{_STATIC_URL_PATH}/bamartech-card.js?v={_CARD_VERSION}"

# Filesystem path to the bundled lovelace assets directory
_LOVELACE_STATIC_DIR = Path(__file__).parent / "lovelace" / "static"

# Process-lifetime guard — static paths cannot be registered twice
_STATIC_PATH_REGISTERED = False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bamartech from a config entry."""
    global _STATIC_PATH_REGISTERED

    coordinator = BamartechCoordinator(hass, entry)

    # First data fetch — with update_interval=None this returns the safe
    # disconnected default immediately.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start the persistent MQTT listener in the background.
    entry.async_create_background_task(
        hass,
        coordinator.async_connect_websocket(),
        name=f"{DOMAIN}_websocket_{entry.entry_id}",
    )

    # ── 1. Serve the bundled JS card as a static asset ───────────────────────
    # Guard against double-registration — HA raises if the same url_path is
    # registered twice within a single process lifetime.
    if not _STATIC_PATH_REGISTERED:
        try:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        url_path=_STATIC_URL_PATH,
                        path=str(_LOVELACE_STATIC_DIR),
                        cache_headers=True,
                    )
                ]
            )
            _STATIC_PATH_REGISTERED = True
            _LOGGER.debug("Bamartech: static path %s registered", _STATIC_URL_PATH)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Bamartech: could not register static path: %s", err)

    # ── 2. Inject the card JS into every HA frontend page load ───────────────
    # add_extra_js_url is idempotent — calling it multiple times with the same
    # URL is safe.  This is the same mechanism HACS uses.
    add_extra_js_url(hass, _CARD_JS_URL)
    _LOGGER.debug("Bamartech: card JS injected via add_extra_js_url: %s", _CARD_JS_URL)

    # ── 3. Register the set_counter service ──────────────────────────────────
    async def _handle_set_counter(call: ServiceCall) -> None:
        """Handle the bamartech.set_counter service call."""
        counter: str = call.data["counter"]
        index:   int = call.data["index"]
        # Apply to every loaded coordinator (typically only one)
        for coord in hass.data.get(DOMAIN, {}).values():
            if isinstance(coord, BamartechCoordinator):
                await coord.async_set_counter(counter, index)

    hass.services.async_register(
        DOMAIN,
        "set_counter",
        _handle_set_counter,
        schema=SET_COUNTER_SCHEMA,
    )

    # ── 4. Register the poll service ─────────────────────────────────────────
    async def _handle_poll(call: ServiceCall) -> None:
        """Handle the bamartech.poll service call."""
        for coord in hass.data.get(DOMAIN, {}).values():
            if isinstance(coord, BamartechCoordinator):
                await coord.async_poll()

    hass.services.async_register(DOMAIN, "poll", _handle_poll)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: BamartechCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_disconnect_websocket()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove the service once the last entry is unloaded
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, "set_counter")
            hass.services.async_remove(DOMAIN, "poll")

    # Remove the JS injection so it doesn't linger after the integration
    # is removed.
    remove_extra_js_url(hass, _CARD_JS_URL)

    return unload_ok
