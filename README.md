# Bamartech — Home Assistant Integration

![Bamartech](custom_components/bamartech/lovelace/static/bamartech-logo.svg)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for the Bamartech sewage treatment plant controller.
Connects to the Bamartech cloud broker over MQTT/WebSockets and exposes real-time
control and monitoring entities inside Home Assistant.

---

## Requirements

- Home Assistant **2024.1.0** or newer
- [HACS](https://hacs.xyz) installed

---

## Installation via HACS

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/rodzikkonrad/bamartech` as an **Integration**.
4. Click **Download** on the Bamartech card.
5. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Bamartech**.
3. Enter your **Login** (the full login string from the Bamartech app) and **Password**.
4. Click **Submit**.

The integration will connect to the cloud broker and create all entities automatically.
No YAML or manual dashboard configuration is required — the custom Lovelace card
is injected automatically on every frontend page load.

---

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.bamartech_status_oczyszczalni` | Binary sensor | Plant connectivity status (PROBLEM class) |
| `switch.bamartech_dmuchawa` | Switch | Blower (Dmuchawa) |
| `switch.bamartech_pompa` | Switch | Pump (Pompa) |
| `switch.bamartech_elektrozawor` | Switch | Solenoid valve (Elektrozawór) |
| `switch.bamartech_wyjscie` | Switch | Output (Wyjście) |
| `sensor.bamartech_czas_pracy` | Sensor | Total uptime in days |
| `sensor.bamartech_wywoz_osadow` | Sensor | Sludge removal countdown (weeks) |
| `sensor.bamartech_biopreparaty` | Sensor | Bio-preparation countdown (days) |
| `sensor.bamartech_konserwacja` | Sensor | Maintenance countdown (weeks) |

---

## Services

### `bamartech.set_counter`

Resets a service counter to a chosen interval.

| Field | Type | Values |
|-------|------|--------|
| `counter` | string | `biopreparaty`, `wywoz_osadow`, `konserwacja` |
| `index` | int (0–3) | 0 = shortest interval, 3 = longest |

---

## License

MIT
