/**
 * bamartech-card — custom Lovelace card for the Bamartech sewage treatment plant
 *
 * Usage (single line in any dashboard):
 *   type: custom:bamartech-card
 *
 * Optional config keys (all have sensible defaults):
 *   binary_sensor       — entity id of the plant_ok binary sensor
 *   switch_blower       — entity id of the Dmuchawa switch
 *   switch_pump         — entity id of the Pompa switch
 *   switch_solenoid     — entity id of the Elektrozawór switch
 *   switch_output       — entity id of the Wyjście switch
 *   sensor_uptime       — entity id of the uptime sensor
 *   sensor_bio          — entity id of the biopreparaty sensor
 *   sensor_wywoz        — entity id of the wywóz osadów sensor
 *   sensor_konserwacja  — entity id of the konserwacja sensor
 */

const CARD_VERSION = "1.0.0";

// ── Default entity IDs (HA slugifies Polish names) ────────────────────────────
const DEFAULTS = {
  binary_sensor:      "binary_sensor.bamartech_status_oczyszczalni",
  switch_blower:      "switch.bamartech_dmuchawa",
  switch_pump:        "switch.bamartech_pompa",
  switch_solenoid:    "switch.bamartech_elektrozawor",
  switch_output:      "switch.bamartech_wyjscie",
  sensor_uptime:      "sensor.bamartech_czas_pracy",
  sensor_bio:         "sensor.bamartech_biopreparaty",
  sensor_wywoz:       "sensor.bamartech_wywoz_osadow",
  sensor_konserwacja: "sensor.bamartech_konserwacja",
};

// ── Reset options per counter ─────────────────────────────────────────────────
const RESET_OPTIONS = {
  biopreparaty:  ["1 tydzień", "2 tygodnie", "3 tygodnie", "4 tygodnie"],
  wywoz_osadow:  ["3 miesiące", "6 miesięcy", "9 miesięcy", "12 miesięcy"],
  konserwacja:   ["3 miesiące", "6 miesięcy", "9 miesięcy", "12 miesięcy"],
};

const RESET_TITLES = {
  biopreparaty:  "Biopreparaty",
  wywoz_osadow:  "Wywóz osadów",
  konserwacja:   "Konserwacja",
};

// ── Styles ────────────────────────────────────────────────────────────────────
const STYLE = `
  :host { display: block; }

  ha-card {
    padding: 16px;
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
  }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .brand-logo { height: 36px; width: auto; display: block; }

  .refresh-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 6px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--secondary-text-color);
    transition: background 0.15s, color 0.15s;
    --mdi-icon-size: 20px;
  }
  .refresh-btn:hover  { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .refresh-btn:active { background: var(--divider-color); }
  .refresh-btn.spinning ha-icon { animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Status banner ── */
  .status-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-radius: 10px;
    margin-bottom: 14px;
    font-size: 14px;
    font-weight: 600;
  }
  .status-ok      { background: #eafaf1; color: #1e8449; }
  .status-problem { background: #fdecea; color: #c0392b; }
  .status-unknown { background: var(--secondary-background-color); color: var(--secondary-text-color); }

  /* ── Switch grid ── */
  .switch-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 14px;
  }

  .switch-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    border-radius: 12px;
    border: none;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: filter 0.15s;
    background: var(--card-background-color, #fff);
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    color: var(--primary-text-color);
    width: 100%;
    text-align: left;
  }
  .switch-btn:hover  { filter: brightness(0.95); }
  .switch-btn:active { filter: brightness(0.88); }
  .switch-btn.on     { background: #eafaf1; }
  .switch-btn.off    { background: var(--card-background-color, #fff); }
  .switch-btn.unavailable { opacity: 0.45; cursor: default; }

  .switch-left { display: flex; align-items: center; gap: 8px; }
  .switch-icon { --mdi-icon-size: 22px; }
  .switch-icon.on  { color: #27ae60; }
  .switch-icon.off { color: var(--secondary-text-color); }

  .switch-pill {
    font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
    padding: 2px 7px; border-radius: 20px;
  }
  .switch-pill.on  { background: #27ae60; color: #fff; }
  .switch-pill.off { background: #e0e0e0; color: #555; }

  /* ── Sensors ── */
  .sensors-title {
    font-size: 13px; font-weight: 700; letter-spacing: 0.5px;
    color: var(--secondary-text-color); text-transform: uppercase;
    margin-bottom: 8px;
  }
  .sensor-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 4px;
    border-bottom: 1px solid var(--divider-color, #eee);
    font-size: 14px;
  }
  .sensor-row:last-child { border-bottom: none; }
  .sensor-left { display: flex; align-items: center; gap: 8px; color: var(--primary-text-color); flex: 1; }
  .sensor-icon { --mdi-icon-size: 18px; color: var(--secondary-text-color); }

  .sensor-right { display: flex; align-items: center; gap: 8px; }
  .sensor-value { font-weight: 700; color: var(--primary-text-color); }

  .reset-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--secondary-text-color);
    transition: background 0.15s, color 0.15s;
    --mdi-icon-size: 18px;
  }
  .reset-btn:hover  { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .reset-btn:active { background: var(--divider-color); }

  /* ── Footer ── */
  .footer {
    margin-top: 14px; text-align: center;
    font-size: 12px; color: var(--secondary-text-color); letter-spacing: 1px;
  }

  /* ── Dialog ── */
  .reset-dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 9998;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .reset-dialog {
    background: var(--card-background-color, #fff);
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.22);
    min-width: 280px;
    max-width: 340px;
    width: 90vw;
    z-index: 9999;
    overflow: hidden;
  }
  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 16px 12px;
    border-bottom: 1px solid var(--divider-color, #eee);
  }
  .dialog-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--primary-text-color);
  }
  .dialog-close {
    background: none; border: none; cursor: pointer;
    color: var(--secondary-text-color); padding: 2px;
    border-radius: 4px; display: flex; align-items: center;
    --mdi-icon-size: 20px;
  }
  .dialog-close:hover { color: var(--primary-text-color); }
  .dialog-options { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
  .dialog-option {
    width: 100%;
    padding: 11px 14px;
    border-radius: 10px;
    border: 1.5px solid var(--divider-color, #ddd);
    background: var(--card-background-color, #fff);
    font-size: 14px;
    font-weight: 600;
    color: var(--primary-text-color);
    cursor: pointer;
    text-align: left;
    transition: background 0.13s, border-color 0.13s;
  }
  .dialog-option:hover  { background: #eafaf1; border-color: #27ae60; color: #1e8449; }
  .dialog-option:active { background: #d5f5e3; }
  .dialog-footer {
    padding: 8px 12px 14px;
    display: flex;
    justify-content: flex-end;
  }
  .dialog-cancel {
    background: none; border: none; cursor: pointer;
    font-size: 14px; font-weight: 600;
    color: var(--secondary-text-color);
    padding: 6px 12px; border-radius: 8px;
  }
  .dialog-cancel:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
`;

// ── Helper: create a Material Design icon element ─────────────────────────────
function mkIcon(name, cls = "") {
  const el = document.createElement("ha-icon");
  el.setAttribute("icon", `mdi:${name}`);
  if (cls) el.className = cls;
  return el;
}

// ── The card element ──────────────────────────────────────────────────────────
class BamartechCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
    this._dialog = null; // currently open dialog overlay element
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 5; }
  static getConfigElement() { return null; }
  static getStubConfig()    { return {}; }

  // ── Open the reset dialog ─────────────────────────────────────────────────
  _openDialog(counter) {
    if (this._dialog) return; // already open

    const root    = this.shadowRoot;
    const options = RESET_OPTIONS[counter];
    const title   = RESET_TITLES[counter];

    const overlay = document.createElement("div");
    overlay.className = "reset-dialog-overlay";

    const box = document.createElement("div");
    box.className = "reset-dialog";

    // Header
    const header = document.createElement("div");
    header.className = "dialog-header";
    const titleEl = document.createElement("span");
    titleEl.className = "dialog-title";
    titleEl.textContent = `Resetuj: ${title}`;
    const closeBtn = document.createElement("button");
    closeBtn.className = "dialog-close";
    closeBtn.appendChild(mkIcon("close"));
    closeBtn.addEventListener("click", () => this._closeDialog());
    header.appendChild(titleEl);
    header.appendChild(closeBtn);
    box.appendChild(header);

    // Options
    const optionsEl = document.createElement("div");
    optionsEl.className = "dialog-options";
    options.forEach((label, index) => {
      const btn = document.createElement("button");
      btn.className = "dialog-option";
      btn.textContent = label;
      btn.addEventListener("click", () => {
        this._hass.callService("bamartech", "set_counter", {
          counter,
          index,
        });
        this._closeDialog();
      });
      optionsEl.appendChild(btn);
    });
    box.appendChild(optionsEl);

    // Footer with cancel
    const footer = document.createElement("div");
    footer.className = "dialog-footer";
    const cancelBtn = document.createElement("button");
    cancelBtn.className = "dialog-cancel";
    cancelBtn.textContent = "Anuluj";
    cancelBtn.addEventListener("click", () => this._closeDialog());
    footer.appendChild(cancelBtn);
    box.appendChild(footer);

    overlay.appendChild(box);

    // Close on backdrop click (outside box)
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._closeDialog();
    });

    root.appendChild(overlay);
    this._dialog = overlay;
  }

  _closeDialog() {
    if (this._dialog) {
      this._dialog.remove();
      this._dialog = null;
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  _render() {
    if (!this._config) return;

    // Keep dialog alive across re-renders triggered by state changes
    const existingDialog = this._dialog;

    const hass = this._hass;
    const cfg  = this._config;

    const stateOf  = (id) => hass?.states?.[id];
    const isOn     = (id) => stateOf(id)?.state === "on";
    const isAvail  = (id) => { const s = stateOf(id); return s && s.state !== "unavailable"; };
    const numValue = (id) => {
      const s = stateOf(id);
      if (!s || s.state === "unavailable" || s.state === "unknown") return "—";
      return `${s.state} ${s.attributes?.unit_of_measurement ?? ""}`.trim();
    };

    const bsState  = stateOf(cfg.binary_sensor);
    const bsStatus = !bsState        ? "unknown"
                   : bsState.state === "off" ? "ok"
                   : bsState.state === "on"  ? "problem"
                   : "unknown";

    // ── Rebuild shadow DOM ────────────────────────────────────────────────
    const root = this.shadowRoot;
    root.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLE;
    root.appendChild(style);

    const card = document.createElement("ha-card");

    // ── Header ──────────────────────────────────────────────────────────
    const header = document.createElement("div");
    header.className = "header";
    const logo = document.createElement("img");
    logo.src = "/bamartech_static/bamartech-logo.svg";
    logo.alt = "Bamartech";
    logo.className = "brand-logo";
    header.appendChild(logo);

    if (hass) {
      const refreshBtn = document.createElement("button");
      refreshBtn.className = "refresh-btn";
      refreshBtn.title = "Odśwież stan";
      refreshBtn.appendChild(mkIcon("refresh"));
      refreshBtn.addEventListener("click", () => {
        refreshBtn.classList.add("spinning");
        hass.callService("bamartech", "poll", {});
        setTimeout(() => refreshBtn.classList.remove("spinning"), 1500);
      });
      header.appendChild(refreshBtn);
    }

    card.appendChild(header);

    // ── Status banner ───────────────────────────────────────────────────
    const banner = document.createElement("div");
    if (bsStatus === "ok") {
      banner.className = "status-banner status-ok";
      banner.innerHTML = `<span>Oczyszczalnia działa poprawnie</span>`;
      banner.appendChild(mkIcon("check-circle"));
    } else if (bsStatus === "problem") {
      banner.className = "status-banner status-problem";
      banner.innerHTML = `<span>Oczyszczalnia nie działa poprawnie</span>`;
      banner.appendChild(mkIcon("alert-circle"));
    } else {
      banner.className = "status-banner status-unknown";
      banner.innerHTML = `<span>Brak połączenia z urządzeniem</span>`;
      banner.appendChild(mkIcon("wifi-off"));
    }
    card.appendChild(banner);

    // ── Switch grid ─────────────────────────────────────────────────────
    const switchDefs = [
      { key: "switch_blower",   label: "Dmuchawa",     mdi: "air-filter"       },
      { key: "switch_pump",     label: "Pompa",         mdi: "pump"             },
      { key: "switch_solenoid", label: "Elektrozawór",  mdi: "electric-switch"  },
      { key: "switch_output",   label: "Wyjście",       mdi: "export"           },
    ];

    const grid = document.createElement("div");
    grid.className = "switch-grid";

    for (const def of switchDefs) {
      const entityId = cfg[def.key];
      const on       = isOn(entityId);
      const avail    = isAvail(entityId);

      const btn = document.createElement("button");
      btn.className = `switch-btn ${on ? "on" : "off"}${!avail ? " unavailable" : ""}`;

      const left = document.createElement("div");
      left.className = "switch-left";
      left.appendChild(mkIcon(def.mdi, `switch-icon ${on ? "on" : "off"}`));
      const lbl = document.createElement("span");
      lbl.textContent = def.label;
      left.appendChild(lbl);

      const pill = document.createElement("span");
      pill.className = `switch-pill ${on ? "on" : "off"}`;
      pill.textContent = on ? "WŁ" : "WYŁ";

      btn.appendChild(left);
      btn.appendChild(pill);

      if (avail && hass) {
        btn.addEventListener("click", () => {
          hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: entityId });
        });
      }

      grid.appendChild(btn);
    }
    card.appendChild(grid);

    // ── Service counters ─────────────────────────────────────────────────
    // Order: Czas pracy (read-only), Biopreparaty, Wywóz osadów, Konserwacja
    const sensorsTitle = document.createElement("div");
    sensorsTitle.className = "sensors-title";
    sensorsTitle.textContent = "Liczniki serwisowe";
    card.appendChild(sensorsTitle);

    const sensorDefs = [
      { key: "sensor_uptime",      label: "Czas pracy",   mdi: "timer-outline", counter: null            },
      { key: "sensor_bio",         label: "Biopreparaty", mdi: "flask",         counter: "biopreparaty"  },
      { key: "sensor_wywoz",       label: "Wywóz osadów", mdi: "delete-clock",  counter: "wywoz_osadow"  },
      { key: "sensor_konserwacja", label: "Konserwacja",  mdi: "wrench-clock",  counter: "konserwacja"   },
    ];

    for (const def of sensorDefs) {
      const row = document.createElement("div");
      row.className = "sensor-row";

      const left = document.createElement("div");
      left.className = "sensor-left";
      left.appendChild(mkIcon(def.mdi, "sensor-icon"));
      const lbl = document.createElement("span");
      lbl.textContent = def.label;
      left.appendChild(lbl);

      const right = document.createElement("div");
      right.className = "sensor-right";

      const val = document.createElement("span");
      val.className = "sensor-value";
      val.textContent = numValue(cfg[def.key]);
      right.appendChild(val);

      // Reset button — only for resettable counters
      if (def.counter && hass) {
        const resetBtn = document.createElement("button");
        resetBtn.className = "reset-btn";
        resetBtn.title = `Resetuj: ${def.label}`;
        resetBtn.appendChild(mkIcon("restore"));
        resetBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          this._openDialog(def.counter);
        });
        right.appendChild(resetBtn);
      }

      row.appendChild(left);
      row.appendChild(right);
      card.appendChild(row);
    }

    // ── Footer ───────────────────────────────────────────────────────────
    const footer = document.createElement("div");
    footer.className = "footer";
    footer.textContent = "bamartech.pl";
    card.appendChild(footer);

    root.appendChild(card);

    // Re-attach dialog if it was open before re-render
    if (existingDialog) {
      root.appendChild(existingDialog);
      this._dialog = existingDialog;
    }
  }
}

customElements.define("bamartech-card", BamartechCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        "bamartech-card",
  name:        "Bamartech",
  description: "Oczyszczalnia ścieków Bamartech — sterowanie i liczniki serwisowe",
  preview:     false,
});

console.info(
  `%c BAMARTECH-CARD %c v${CARD_VERSION} `,
  "background:#c0392b;color:#fff;font-weight:700;padding:2px 4px;border-radius:3px 0 0 3px",
  "background:#2c3e50;color:#fff;font-weight:400;padding:2px 4px;border-radius:0 3px 3px 0",
);
