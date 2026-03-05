"""DataUpdateCoordinator for the Bamartech integration.

Architecture
------------
Transport  : MQTT over WebSockets (paho-mqtt, MQTTv3.1.1)
Broker     : lentecdesignbamw.com.pl:9001  (fixed — cloud server)
Auth       : username = "tel" + login[0:6]
             password = as entered in config flow
Device ID  : login[6:38]  (32-char hex string)

Topics
------
  ser/{device_id}_out  — device → HA  (state broadcasts, ~every 5 min)
  {device_id}_in       — HA → device  (commands; NO "ser/" prefix)

Received message format
-----------------------
  {message:XXXXXXXXXXXXXXXXXXXXXXXXXXXX}
  24 hex chars = 12 bytes (11 data bytes + 1 Dallas/Maxim CRC-8)

  Byte  0 : WersjaInterfejsuKomunikacji — always 0x01
  Byte  1 : TypOczyszczalni             — always 0x11
  Byte  2 : StanyWyjsc output bitmask   (0x01=Dmuchawa, 0x02=Pompa,
                                         0x04=Elektrozawór, 0x08=Wyjście)
  Bytes 4-5: uptime 16-bit LE, days
  Byte  8 : ZaIleTygodniSerwis          — maintenance countdown (weeks)
  Byte  9 : ZaIleDniBiopreparaty        — bio-prep countdown (days)
  Byte 10 : ZaIleTygodniWywozOsadow     — sludge removal countdown (weeks)
  Byte 11 : Dallas/Maxim CRC-8 (poly 0x8C) of bytes 0–10

Command format (HA → device) — confirmed from wire capture
----------------------------------------------------------
  Plain 12-char ASCII hex string (6 bytes, no {message:…} wrapper):

  byte[0] = 0x01                   (version, always)
  byte[1] = 0x11                   (plant type, always)
  byte[2] = 0x10 | output_bit
  byte[3] = output_bit if (output_bit == POMPA and turning ON) else 0x00
  byte[4] = _cmd_seq  (incremented before every publish)
  byte[5] = Dallas/Maxim CRC-8 (poly 0x8C) of bytes 0–4

  Example: Elektrozawor ON, seq=4 → "0111140004CF"

  Status poll (output_bit=0x00): byte[2]=0x10, byte[3]=0x00
    Sent automatically on connect — triggers an immediate state broadcast
    from the device instead of waiting for the next periodic one (~5 min).
    seq=1 example → "01111000016E"

Reset formats (all confirmed from wire capture)
------------------------------------------------------------
  Same 6-byte / 12-char structure for all three counters:

  biopreparaty  (index 0–3 → weeks 1–4):
    byte[2] = 0x50,  byte[3] = (weeks - 1) << 2
    (0x00 / 0x04 / 0x08 / 0x0C)

  konserwacja   (index 0–3 → months 3/6/9/12):
    byte[2] = 0x90,  byte[3] = (months // 3 - 1) << 2
    (0x00 / 0x04 / 0x08 / 0x0C)

  wywoz_osadow  (index 0–3 → months 3/6/9/12):
    byte[2] = 0xD0,  byte[3] = (months // 3 - 1) << 2
    (0x00 / 0x04 / 0x08 / 0x0C)

  byte[4] = _cmd_seq (same counter series as output commands)
  byte[5] = CRC of bytes 0–4
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BITMASK_BLOWER,
    BITMASK_OUTPUT,
    BITMASK_PUMP,
    BITMASK_SOLENOID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    WS_MAX_RECONNECT_ATTEMPTS,
    WS_RECONNECT_DELAY,
)

_LOGGER = logging.getLogger(__name__)

_MESSAGE_RE = re.compile(r"\{message:([0-9A-Fa-f]{24,})\}")

# Safe "disconnected" data returned before the first MQTT packet arrives
_DISCONNECTED_DATA: dict[str, Any] = {
    "connected":    False,
    "plant_ok":     False,
    "dmuchawa":     False,
    "pompa":        False,
    "elektrozawor": False,
    "wyjscie":      False,
    "uptime_days":  None,
    "wywoz_osadow": None,
    "biopreparaty": None,
    "konserwacja":  None,
}


# ---------------------------------------------------------------------------
# CRC helper
# ---------------------------------------------------------------------------

def _calculate_crc(data_bytes: list[int]) -> int:
    """Dallas/Maxim 1-Wire XOR-8 CRC over the 11 data bytes."""
    crc = 0
    for byte in data_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
    return crc


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class BamartechCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage state for the Bamartech integration via MQTT-over-WebSockets."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator and derive MQTT parameters from login."""
        # Disable periodic polling — device pushes state on its own schedule
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=None,
        )

        login = entry.data[CONF_USERNAME]
        self._mqtt_username: str  = "tel" + login[0:6]
        self._mqtt_password: str  = entry.data[CONF_PASSWORD]
        self._device_id: str      = login[6:38]
        self._topic_out: str      = f"ser/{self._device_id}_out"
        self._topic_in: str       = f"{self._device_id}_in"   # NO "ser/" prefix

        # Sequential command counter — incremented before every publish
        self._cmd_seq: int = 0

        self._mqtt_client: mqtt.Client | None = None
        self._ws_connected: bool = False
        self._shutdown: bool = False
        self._reconnect_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hook — no HTTP polling, return cached data
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Return the most recently received device state.

        Since the device pushes via MQTT we never actively poll.
        This method is only called by the coordinator on startup for
        the first_refresh(); we return the safe disconnected default.
        """
        return self.data if self.data is not None else dict(_DISCONNECTED_DATA)

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_message(payload: str) -> dict[str, Any] | None:
        """Parse a raw MQTT payload string into a state dict.

        Returns None if the payload does not contain a valid message frame.
        """
        match = _MESSAGE_RE.search(payload)
        if not match:
            return None

        hex_str = match.group(1)
        if len(hex_str) < 24:
            return None

        data = [int(hex_str[i:i + 2], 16) for i in range(0, 22, 2)]  # 11 bytes
        outputs   = data[2]
        uptime    = data[4] | (data[5] << 8)

        return {
            "connected":    True,
            "plant_ok":     True,   # connected ⇒ plant OK (option A)
            "dmuchawa":     bool(outputs & BITMASK_BLOWER),
            "pompa":        bool(outputs & BITMASK_PUMP),
            "elektrozawor": bool(outputs & BITMASK_SOLENOID),
            "wyjscie":      bool(outputs & BITMASK_OUTPUT),
            "uptime_days":  uptime,
            "konserwacja":  data[8],    # weeks  (byte 8 = ZaIleTygodniSerwis)
            "biopreparaty": data[9],    # days   (byte 9 = ZaIleDniBiopreparaty)
            "wywoz_osadow": data[10],   # weeks  (byte 10 = ZaIleTygodniWywozOsadow)
        }

    # ------------------------------------------------------------------
    # MQTT callbacks  (called from paho's network thread)
    # ------------------------------------------------------------------

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        # reason_code is an int (paho 1.x) or ReasonCode object (paho 2.x);
        # in both cases falsy/zero means success.
        failed = reason_code.is_failure if hasattr(reason_code, "is_failure") else bool(reason_code)
        if not failed:
            _LOGGER.info("Bamartech: MQTT connected (broker %s:%s)", DEFAULT_HOST, DEFAULT_PORT)
            client.subscribe(self._topic_out)
            _LOGGER.debug("Bamartech: subscribed to %s", self._topic_out)
            self._ws_connected = True
            # Push a "connected but no data yet" update so availability shows up
            self.hass.loop.call_soon_threadsafe(
                self.async_set_updated_data,
                {**(self.data or _DISCONNECTED_DATA), "connected": True, "plant_ok": True},
            )
            # Send status poll so the device replies immediately instead of
            # waiting up to 5 min for the next periodic broadcast.
            # byte[2]=0x10, byte[3]=0x00, output_bit=0x00 — confirmed wire format.
            self._cmd_seq += 1
            poll_data = [0x01, 0x11, 0x10, 0x00, self._cmd_seq & 0xFF]
            poll_crc = _calculate_crc(poll_data)
            poll_payload = "".join(f"{b:02X}" for b in poll_data) + f"{poll_crc:02X}"
            client.publish(self._topic_in, poll_payload, 0)
            _LOGGER.debug("Bamartech: sent status poll → %s (seq=%d)", poll_payload, self._cmd_seq)
        else:
            _LOGGER.warning("Bamartech: MQTT connection refused rc=%s", reason_code)
            self._ws_connected = False

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags_or_rc: Any,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        # paho 1.x: (client, userdata, rc)
        # paho 2.x: (client, userdata, disconnect_flags, reason_code, properties)
        self._ws_connected = False
        _LOGGER.warning("Bamartech: MQTT disconnected rc=%s", reason_code or disconnect_flags_or_rc)
        # Mark entities unavailable
        self.hass.loop.call_soon_threadsafe(
            self.async_set_updated_data,
            dict(_DISCONNECTED_DATA),
        )
        # Schedule reconnect unless we are shutting down
        if not self._shutdown:
            self.hass.loop.call_soon_threadsafe(self._schedule_reconnect)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
            _LOGGER.debug("Bamartech: MQTT message on %s: %s", msg.topic, payload)

            parsed = self._parse_message(payload)
            if parsed is None:
                _LOGGER.debug("Bamartech: could not parse message, ignoring")
                return

            self.hass.loop.call_soon_threadsafe(
                self.async_set_updated_data, parsed
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bamartech: error handling MQTT message")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _build_client(self) -> mqtt.Client:
        """Create and configure a paho MQTT client.

        Uses CallbackAPIVersion.VERSION2 when available (paho-mqtt >= 2.0)
        and falls back silently to the legacy API for older installs.
        """
        kwargs: dict[str, Any] = {
            "transport": "websockets",
            "protocol":  mqtt.MQTTv311,
        }
        if hasattr(mqtt, "CallbackAPIVersion"):
            kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION2

        client = mqtt.Client(**kwargs)
        client.username_pw_set(self._mqtt_username, self._mqtt_password)
        client.on_connect    = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message    = self._on_message
        return client

    async def async_connect_websocket(self) -> None:
        """Connect to the MQTT broker and keep the connection alive.

        Runs as a long-lived background task created in __init__.py.
        Uses paho's threaded network loop so the HA event loop is never
        blocked.  Callbacks bridge back to the event loop via
        call_soon_threadsafe().
        """
        attempts = 0

        while not self._shutdown:
            if attempts >= WS_MAX_RECONNECT_ATTEMPTS:
                _LOGGER.error(
                    "Bamartech: giving up after %d connection attempts", attempts
                )
                break

            try:
                _LOGGER.debug(
                    "Bamartech: connecting to %s:%s as %s (attempt %d)",
                    DEFAULT_HOST, DEFAULT_PORT, self._mqtt_username, attempts + 1,
                )
                client = self._build_client()
                self._mqtt_client = client

                # connect() is a blocking network call — run it off the event loop
                await self.hass.async_add_executor_job(
                    client.connect, DEFAULT_HOST, DEFAULT_PORT, 60
                )
                client.loop_start()

                # Wait here until disconnected or shutdown is requested
                while not self._shutdown and (self._ws_connected or attempts == 0):
                    await asyncio.sleep(1)
                    # If paho reports not connected after first connect, break out
                    if not self._ws_connected and attempts == 0:
                        # Give it a moment to connect
                        await asyncio.sleep(WS_RECONNECT_DELAY)
                        if not self._ws_connected:
                            break

                if self._shutdown:
                    break

                # Disconnected — stop the old client and reconnect
                client.loop_stop()
                attempts += 1

            except asyncio.CancelledError:
                _LOGGER.debug("Bamartech: connection task cancelled")
                break
            except Exception as err:  # noqa: BLE001
                self._ws_connected = False
                attempts += 1
                _LOGGER.warning(
                    "Bamartech: connection error (%s), retrying in %ds (attempt %d/%d)",
                    err, WS_RECONNECT_DELAY, attempts, WS_MAX_RECONNECT_ATTEMPTS,
                )
                await asyncio.sleep(WS_RECONNECT_DELAY)

        self._ws_connected = False

    def _schedule_reconnect(self) -> None:
        """Called from the event loop when paho fires _on_disconnect."""
        if self._shutdown:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = self.hass.async_create_task(
            self._reconnect_after_delay()
        )

    async def _reconnect_after_delay(self) -> None:
        """Wait, then attempt to reconnect the MQTT client."""
        await asyncio.sleep(WS_RECONNECT_DELAY)
        if self._shutdown or self._ws_connected:
            return
        if self._mqtt_client is not None:
            try:
                _LOGGER.debug("Bamartech: attempting reconnect")
                await self.hass.async_add_executor_job(self._mqtt_client.reconnect)
                self._mqtt_client.loop_start()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Bamartech: reconnect failed: %s", err)
                # Schedule another attempt
                self._schedule_reconnect()

    async def async_disconnect_websocket(self) -> None:
        """Stop the MQTT client cleanly."""
        self._shutdown = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._mqtt_client is not None:
            try:
                await self.hass.async_add_executor_job(self._mqtt_client.loop_stop)
                await self.hass.async_add_executor_job(self._mqtt_client.disconnect)
            except Exception:  # noqa: BLE001
                pass
            self._mqtt_client = None
        self._ws_connected = False
        _LOGGER.debug("Bamartech: MQTT disconnected cleanly")

    # ------------------------------------------------------------------
    # Command dispatch — called by switch entities and service handlers
    # ------------------------------------------------------------------

    async def async_poll(self) -> None:
        """Send a status poll command to trigger an immediate state broadcast.

        Identical to the poll sent automatically on connect:
          byte[2] = 0x10, byte[3] = 0x00  (output_bit = 0x00)
        The device responds with its current full state within ~1 second.
        """
        if self._mqtt_client is None or not self._ws_connected:
            _LOGGER.warning("Bamartech: cannot send poll — MQTT not connected")
            return

        self._cmd_seq += 1
        data = [0x01, 0x11, 0x10, 0x00, self._cmd_seq & 0xFF]
        crc = _calculate_crc(data)
        hex_payload = "".join(f"{b:02X}" for b in data) + f"{crc:02X}"

        _LOGGER.debug("Bamartech: sending status poll → %s (seq=%d)", hex_payload, self._cmd_seq)

        await self.hass.async_add_executor_job(
            self._mqtt_client.publish, self._topic_in, hex_payload, 0
        )

    async def async_set_counter(self, counter: str, index: int) -> None:
        """Reset a service counter on the device.

        `index` is 0–3.  Each counter maps it differently:

          biopreparaty  — weeks 1–4:        index + 1
            byte[2] = 0x50,  byte[3] = (weeks - 1) << 2

          konserwacja   — months 3/6/9/12:  (index + 1) * 3
            byte[2] = 0x90,  byte[3] = (months // 3 - 1) << 2

          wywoz_osadow  — months 3/6/9/12:  (index + 1) * 3
            byte[2] = 0xD0,  byte[3] = (months // 3 - 1) << 2

        All three share the same 6-byte frame structure with _cmd_seq at
        byte[4] and Dallas/Maxim CRC-8 at byte[5].
        """
        if self._mqtt_client is None or not self._ws_connected:
            _LOGGER.warning("Bamartech: cannot send counter reset — MQTT not connected")
            return

        idx = max(0, min(3, int(index)))   # clamp to 0–3

        if counter == "biopreparaty":
            weeks = idx + 1                # 1–4
            cmd_byte = 0x50
            val_byte = (weeks - 1) << 2
            label = f"weeks={weeks}"
        elif counter == "konserwacja":
            months = (idx + 1) * 3         # 3/6/9/12
            cmd_byte = 0x90
            val_byte = (months // 3 - 1) << 2
            label = f"months={months}"
        elif counter == "wywoz_osadow":
            months = (idx + 1) * 3         # 3/6/9/12
            cmd_byte = 0xD0
            val_byte = (months // 3 - 1) << 2
            label = f"months={months}"
        else:
            _LOGGER.error("Bamartech: unknown counter '%s'", counter)
            return

        self._cmd_seq += 1
        data = [0x01, 0x11, cmd_byte, val_byte, self._cmd_seq & 0xFF]
        crc = _calculate_crc(data)
        hex_payload = "".join(f"{b:02X}" for b in data) + f"{crc:02X}"

        _LOGGER.debug(
            "Bamartech: resetting counter %s (%s) → %s (seq=%d)",
            counter, label, hex_payload, self._cmd_seq,
        )

        await self.hass.async_add_executor_job(
            self._mqtt_client.publish, self._topic_in, hex_payload, 0
        )

    async def async_set_output(self, bitmask: int, turn_on: bool) -> None:
        """Turn a single output on or off.

        Builds the confirmed 6-byte / 12-char ASCII hex command payload:
          byte[0] = 0x01  (version)
          byte[1] = 0x11  (plant type)
          byte[2] = 0x10 | bitmask
          byte[3] = bitmask if (bitmask == POMPA and turning ON) else 0x00
          byte[4] = _cmd_seq  (incremented before send)
          byte[5] = Dallas/Maxim CRC-8 of bytes 0–4

        Published as a plain hex string (no {message:…} wrapper) to
        {device_id}_in (no "ser/" prefix).
        """
        if self._mqtt_client is None or not self._ws_connected:
            _LOGGER.warning("Bamartech: cannot send command — MQTT not connected")
            return

        self._cmd_seq += 1
        b3 = bitmask if (bitmask == BITMASK_PUMP and turn_on) else 0x00
        data = [0x01, 0x11, 0x10 | bitmask, b3, self._cmd_seq & 0xFF]
        crc = _calculate_crc(data)
        hex_payload = "".join(f"{b:02X}" for b in data) + f"{crc:02X}"

        _LOGGER.debug(
            "Bamartech: publishing command to %s: %s (seq=%d, on=%s)",
            self._topic_in, hex_payload, self._cmd_seq, turn_on,
        )

        await self.hass.async_add_executor_job(
            self._mqtt_client.publish, self._topic_in, hex_payload, 0
        )
