const cardType = "zakarpattia-outages-card";
const queues = Array.from({ length: 12 }, (_, i) => `${Math.floor(i / 2) + 1}.${i % 2 + 1}`);
const hours = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0"));
const confirmedRow = /^[01]{48}$/;
const displayDate = (day) => day ? day.split("-").reverse().join(".") : "";
const isoDay = /^\d{4}-\d{2}-\d{2}$/;

const labels = {
  uk: {
    title: "Графік відключень Закарпаття",
    today: "Сьогодні",
    tomorrow: "Завтра",
    queue: "Підчерга",
    outage: "Відключення за графіком",
    clear: "Відключення не заплановано",
    unknown: "Графік не опубліковано",
    offline: "Дані графіка недоступні",
  },
  en: {
    title: "Zakarpattia outage schedule",
    today: "Today",
    tomorrow: "Tomorrow",
    queue: "Subqueue",
    outage: "Scheduled outage",
    clear: "No scheduled outage",
    unknown: "Schedule not published",
    offline: "Schedule data unavailable",
  },
};

const styles = `
  ha-card { overflow: hidden; color: var(--primary-text-color); }
  .heading { padding: 18px 16px 10px; }
  h2 { margin: 0; font-size: 1.2rem; font-weight: 600; line-height: 1.35; }
  .days { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 16px 12px; }
  button {
    color: inherit; background: transparent; padding: 7px 12px; cursor: pointer;
    border: 1px solid var(--divider-color, #777); border-radius: 999px; font: inherit;
  }
  button[aria-pressed="true"] {
    border-color: var(--primary-color, #1682aa);
    background: color-mix(in srgb, var(--primary-color, #1682aa) 16%, transparent);
    font-weight: 600;
  }
  .scroll { overflow: auto; padding: 0 16px; }
  table { border-spacing: 0; table-layout: fixed; width: 100%; min-width: 850px; }
  th { font-size: 12px; font-variant-numeric: tabular-nums; }
  th, td { border-bottom: 1px solid var(--divider-color, #8887); box-sizing: border-box; }
  th[scope="row"], .queue {
    width: 82px; padding: 0 8px; text-align: left; position: sticky; left: 0;
    background: var(--ha-card-background, var(--card-background-color, Canvas)); z-index: 1;
  }
  th[scope="colgroup"] { border-left: 1px solid var(--divider-color, #8887); height: 26px; }
  td { height: 24px; }
  td:nth-child(even) { border-left: 1px solid var(--divider-color, #8887); }
  .outage { background: #d76638; }
  .clear { background: color-mix(in srgb, var(--success-color, #568067) 20%, transparent); }
  .unknown { background: repeating-linear-gradient(130deg, #8882 0 3px, transparent 3px 7px); }
  tr.selected > * {
    border-top: 2px solid var(--primary-color, #1682aa);
    border-bottom: 2px solid var(--primary-color, #1682aa);
  }
  tr.selected th {
    color: var(--primary-color, #1682aa);
    border-left: 3px solid currentColor; font-weight: 800;
  }
  tr.selected td:last-child { border-right: 2px solid var(--primary-color, #1682aa); }
  .legend {
    display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 12px 16px 16px;
    margin: 0; list-style: none; font-size: 12px;
  }
  .legend li { display: inline-flex; align-items: center; gap: 6px; }
  .swatch { width: 13px; height: 13px; border-radius: 3px; border: 1px solid #8885; }
  .notice { padding: 0 16px 12px; margin: 0; color: var(--secondary-text-color); }
`;

class ZakarpattiaOutagesCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._dayIndex = 0;
    this.shadowRoot.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-day]");
      if (button) {
        this._dayIndex = Number(button.dataset.day);
        this._render();
        this.shadowRoot.querySelector(`button[data-day="${this._dayIndex}"]`).focus();
      }
    });
  }

  setConfig(config) {
    if (config.entity && typeof config.entity !== "string") {
      throw new Error("entity must be a sensor entity ID");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const { states, locale, language } = this._hass;
    const lang = (locale?.language || language || "en").startsWith("uk") ? "uk" : "en";
    const text = labels[lang];
    const state = this._config.entity
      ? states[this._config.entity]
      : Object.values(states).find(({ attributes }) =>
          queues.includes(attributes.queue) && attributes.all_queues
        );
    const selected = queues.includes(state?.attributes.queue) ? state.attributes.queue : "";
    const schedules = state?.attributes.all_queues ?? {};
    const days = Object.keys(schedules).filter((day) => isoDay.test(day)).sort();
    const date = days[this._dayIndex];
    const rows = schedules[date] ?? {};
    const published = queues.some((queue) => confirmedRow.test(rows[queue]));
    const offline = !state || state.state === "unavailable";
    const key = JSON.stringify([lang, selected, days, rows, offline, this._dayIndex]);
    if (key === this._rendered) return;
    this._rendered = key;
    const scrollLeft = this.shadowRoot.querySelector(".scroll")?.scrollLeft ?? 0;
    const localDate = displayDate(date);
    const dayButtons = [text.today, text.tomorrow].map((label, i) => {
      const formatted = displayDate(days[i]);
      return `<button type="button" data-day="${i}" aria-pressed="${i === this._dayIndex}">${label}${formatted ? ` · ${formatted}` : ""}</button>`;
    }).join("");
    const heading = hours.map((hour) => `<th scope="colgroup" colspan="2">${hour}</th>`).join("");
    const body = queues.map((queue) => {
      const row = rows[queue];
      const cells = this._cells(typeof row === "string" && confirmedRow.test(row) ? row : "", text);
      const highlighted = queue === selected ? ' class="selected" aria-current="true"' : "";
      return `<tr${highlighted}><th scope="row">${queue}</th>${cells}</tr>`;
    }).join("");
    const notice = offline ? text.offline : published ? "" : text.unknown;
    const legend = ["outage", "clear", "unknown"].map((kind) =>
      `<li><span class="swatch ${kind}" aria-hidden="true"></span>${text[kind]}</li>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>${styles}</style>
      <ha-card>
        <div class="heading"><h2>${text.title}${selected ? ` · ${selected}` : ""}</h2></div>
        <div class="days">${dayButtons}</div>
        ${notice ? `<p class="notice" role="status">${notice}</p>` : ""}
        <div class="scroll" tabindex="0" aria-label="${text.title} ${localDate}">
          <table aria-label="${text.title} ${localDate}">
            <thead><tr><th class="queue" scope="col">${text.queue}</th>${heading}</tr></thead>
            <tbody>${body}</tbody>
          </table>
        </div>
        <ul class="legend">${legend}</ul>
      </ha-card>`;
    this.shadowRoot.querySelector(".scroll").scrollLeft = scrollLeft;
  }

  _cells(row, text) {
    return hours.map((hour, i) => [0, 1].map((half) => {
      const state = row ? (row[i * 2 + half] === "1" ? "outage" : "clear") : "unknown";
      const label = `${hour}:${half === 0 ? "00" : "30"} · ${text[state]}`;
      return `<td class="${state}" title="${label}" aria-label="${label}"></td>`;
    }).join("")).join("");
  }
}

if (!customElements.get(cardType)) {
  customElements.define(cardType, ZakarpattiaOutagesCard);
  window.customCards ??= [];
  window.customCards.push({
    type: cardType,
    name: "Zakarpattia Outages",
    description: "Regional outage schedule with your subqueue highlighted.",
  });
}

const panelType = "zakarpattia-outages-panel";

const panelText = {
  uk: {
    title: "Графік світла",
    settings: "Налаштування",
    schedule: "Зараз за графіком",
    grid: "Фактичний стан мережі",
    next: "Наступне відключення",
    restore: "Відновлення за графіком",
    outage_scheduled: "Відключення",
    no_outage_scheduled: "Без відключення",
    unpublished: "Графік не опубліковано",
    on: "Мережа є",
    off: "Мережі немає",
    missing: "Датчик не налаштовано",
    unavailable: "Недоступно",
    noTime: "Час невідомий",
  },
  en: {
    title: "Outage schedule",
    settings: "Settings",
    schedule: "Current schedule",
    grid: "Actual grid status",
    next: "Next scheduled outage",
    restore: "Scheduled restoration",
    outage_scheduled: "Outage",
    no_outage_scheduled: "No outage",
    unpublished: "Schedule not published",
    on: "Grid available",
    off: "Grid unavailable",
    missing: "Sensor not configured",
    unavailable: "Unavailable",
    noTime: "Time unknown",
  },
};

class ZakarpattiaOutagesPanel extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; min-height: 100%; color: var(--primary-text-color); }
        header { display: flex; align-items: center; gap: 12px; padding: 12px 16px;
          min-height: 40px; background: var(--app-header-background-color);
          color: var(--app-header-text-color); }
        h1 { font-size: 20px; font-weight: 500; margin: 0; flex: 1; }
        header a { color: inherit; font-weight: 600; }
        main { box-sizing: border-box; max-width: 1300px; margin: auto; padding: clamp(12px, 3vw, 32px); }
        label { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
        select { padding: 8px 12px; border-radius: 8px; font: inherit; color: inherit;
          border: 1px solid var(--divider-color, #777);
          background: var(--card-background-color, Canvas); }
        dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 175px), 1fr));
          gap: 10px; margin: 0 0 16px; }
        dl div { background: var(--ha-card-background, var(--card-background-color));
          padding: 12px; border: 1px solid var(--divider-color, #777);
          border-radius: var(--ha-card-border-radius, 12px); }
        dt { color: var(--secondary-text-color); font-size: 13px; margin-bottom: 4px; }
        dd { margin: 0; font-size: 16px; font-weight: 600; }
        [hidden] { display: none; }
      </style>
      <header><ha-menu-button></ha-menu-button><h1></h1><a href="/config/integrations/integration/zakarpattia_outages"></a></header>
      <main>
        <label hidden><span></span><select></select></label>
        <dl>
          <div><dt></dt><dd></dd></div><div><dt></dt><dd></dd></div>
          <div><dt></dt><dd></dd></div><div><dt></dt><dd></dd></div>
        </dl>
        <zakarpattia-outages-card></zakarpattia-outages-card>
      </main>`;
    this._select = root.querySelector("select");
    this._card = root.querySelector(cardType);
    this._select.addEventListener("change", () => {
      this._entity = this._select.value;
      this._render();
    });
  }

  set narrow(narrow) {
    this.shadowRoot.querySelector("ha-menu-button").narrow = narrow;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    const { states, locale, language, user } = this._hass;
    const lang = (locale?.language || language || "en").startsWith("uk") ? "uk" : "en";
    const text = panelText[lang];
    const configured = Object.entries(states)
      .filter(([, { attributes }]) => queues.includes(attributes.queue) && attributes.all_queues)
      .sort(([, a], [, b]) => a.attributes.queue.localeCompare(b.attributes.queue));
    const selection = configured.find(([id]) => id === this._entity) || configured[0];
    const [entity, state] = selection || [];
    this._entity = entity;

    const root = this.shadowRoot;
    root.querySelector("ha-menu-button").hass = this._hass;
    root.querySelector("h1").textContent = text.title;
    const settings = root.querySelector("header a");
    settings.textContent = text.settings;
    settings.hidden = !user?.is_admin;
    root.querySelector("label").hidden = configured.length <= 1;
    root.querySelector("label span").textContent = labels[lang].queue;

    const optionsKey = JSON.stringify(configured.map(([id, item]) => [id, item.attributes.queue]));
    if (optionsKey !== this._optionsKey) {
      this._select.replaceChildren(...configured.map(([id, item]) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = item.attributes.queue;
        return option;
      }));
      this._optionsKey = optionsKey;
    }
    Array.from(this._select.options).forEach((option) => {
      option.selected = option.value === entity;
    });

    const grid = state && Object.values(states).find(({ attributes }) =>
      attributes.queue === state.attributes.queue && attributes.grid_power_source
    );
    const formatTime = new Intl.DateTimeFormat(lang, {
      timeZone: "Europe/Kyiv", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    });
    const timestamp = (value) => value && Number.isFinite(Date.parse(value))
      ? formatTime.format(new Date(value))
      : text.noTime;
    const values = [
      [text.schedule, text[state?.state] ?? text.unavailable],
      [text.grid, grid ? (text[grid.state] ?? text.unavailable) : text.missing],
      [text.next, timestamp(state?.attributes.next_outage)],
      [text.restore, timestamp(state?.attributes.next_restoration)],
    ];
    root.querySelectorAll("dl div").forEach((item, i) => {
      item.querySelector("dt").textContent = values[i][0];
      item.querySelector("dd").textContent = values[i][1];
    });

    this._card.setConfig({ entity });
    this._card.hass = this._hass;
  }
}

if (!customElements.get(panelType)) {
  customElements.define(panelType, ZakarpattiaOutagesPanel);
}
