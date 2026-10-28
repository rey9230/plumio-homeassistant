/*
 * Plumio — tags by room card.
 *
 * Where every Plumio tag of the Nest is, grouped by room of the house (from the tag's
 * Room sensor: Bluetooth proxies + Bermuda), then the ones at home in no known room, then
 * the ones away, with where and when a phone last heard them.
 *
 *   type: custom:plumio-tags-card
 *   title: Where are my things?   # optional
 *   show_away: true               # optional
 */

const TEXT = {
  en: {
    name: "Plumio — Tags by room",
    description: "Where each of your Plumio tags is: room by room at home, and the ones that are out.",
    title: "Title (optional)",
    show_away: "Also show tags that are not at home",
    home_unknown_room: "At home, room unknown",
    away: "Away",
    nowhere: "Never heard yet",
    none: "No Plumio tags in this Nest yet.",
    battery_low: "Battery low",
    ago: "ago",
    now: "just now",
  },
  es: {
    name: "Plumio — Tags por habitación",
    description: "Dónde está cada uno de tus tags Plumio: habitación por habitación en casa, y los que están fuera.",
    title: "Título (opcional)",
    show_away: "Mostrar también los tags que no están en casa",
    home_unknown_room: "En casa, habitación desconocida",
    away: "Fuera de casa",
    nowhere: "Aún no se ha oído",
    none: "Todavía no hay tags Plumio en este Nido.",
    battery_low: "Pila baja",
    ago: "",
    now: "ahora mismo",
  },
  de: {
    name: "Plumio — Tags nach Raum",
    description: "Wo jeder deiner Plumio-Tags ist: Raum für Raum zu Hause, und die, die unterwegs sind.",
    title: "Titel (optional)",
    show_away: "Auch Tags zeigen, die nicht zu Hause sind",
    home_unknown_room: "Zu Hause, Raum unbekannt",
    away: "Unterwegs",
    nowhere: "Noch nie gehört",
    none: "Noch keine Plumio-Tags in diesem Nest.",
    battery_low: "Batterie schwach",
    ago: "",
    now: "gerade eben",
  },
  fr: {
    name: "Plumio — Tags par pièce",
    description: "Où se trouve chacun de vos tags Plumio : pièce par pièce à la maison, et ceux qui sont dehors.",
    title: "Titre (facultatif)",
    show_away: "Afficher aussi les tags qui ne sont pas à la maison",
    home_unknown_room: "À la maison, pièce inconnue",
    away: "Hors de la maison",
    nowhere: "Jamais détecté",
    none: "Aucun tag Plumio dans ce Nid pour l’instant.",
    battery_low: "Pile faible",
    ago: "",
    now: "à l’instant",
  },
  it: {
    name: "Plumio — Tag per stanza",
    description: "Dove si trova ognuno dei tuoi tag Plumio: stanza per stanza in casa, e quelli fuori.",
    title: "Titolo (facoltativo)",
    show_away: "Mostra anche i tag che non sono a casa",
    home_unknown_room: "A casa, stanza sconosciuta",
    away: "Fuori casa",
    nowhere: "Mai rilevato",
    none: "Ancora nessun tag Plumio in questo Nido.",
    battery_low: "Batteria scarica",
    ago: "",
    now: "proprio ora",
  },
  pt: {
    name: "Plumio — Tags por cômodo",
    description: "Onde está cada um dos seus tags Plumio: cômodo por cômodo em casa, e os que estão fora.",
    title: "Título (opcional)",
    show_away: "Mostrar também os tags que não estão em casa",
    home_unknown_room: "Em casa, cômodo desconhecido",
    away: "Fora de casa",
    nowhere: "Ainda não detectado",
    none: "Ainda não há tags Plumio neste Ninho.",
    battery_low: "Bateria fraca",
    ago: "",
    now: "agora mesmo",
  },
  "zh-Hant": {
    name: "Plumio — 依房間顯示追蹤器",
    description: "你的每個 Plumio 追蹤器在哪裡：在家時依房間顯示，以及不在家的追蹤器。",
    title: "標題（選填）",
    show_away: "也顯示不在家的追蹤器",
    home_unknown_room: "在家，房間未知",
    away: "不在家",
    nowhere: "尚未偵測到",
    none: "這個巢還沒有 Plumio 追蹤器。",
    battery_low: "電池電量低",
    ago: "",
    now: "剛剛",
  },
};

function textFor(language) {
  const lang = (language || "en").toLowerCase();
  if (lang.startsWith("zh")) return TEXT["zh-Hant"];
  return TEXT[lang.split("-")[0]] || TEXT.en;
}

// A CR2032 is new at about 3.0 V and nearly done below 2.5 V.
const LOW_BATTERY_V = 2.5;
const NO_ROOM = new Set(["", "unknown", "unavailable", "none", "not_home"]);
// The icon keys the Plumio app offers when a tag is added.
const ICONS = {
  keys: "mdi:key-variant",
  backpack: "mdi:bag-personal",
  wallet: "mdi:wallet",
  luggage: "mdi:bag-suitcase",
  pet: "mdi:paw",
  bike: "mdi:bike",
  car: "mdi:car",
  other: "mdi:tag",
};

function escape(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

class PlumioTagsCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "show_away", selector: { boolean: {} } },
      ],
      computeLabel: (schema) => {
        const lang = document.querySelector("home-assistant")?.hass?.locale?.language;
        return textFor(lang)[schema.name] || schema.name;
      },
    };
  }

  static getStubConfig() {
    return { show_away: true };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._signature = null;
  }

  setConfig(config) {
    this._config = { show_away: true, ...config };
    this._signature = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }

  get _t() {
    return textFor(this._hass?.locale?.language);
  }

  /** One entry per Plumio tag device: its tracker, room, battery and last-seen entities. */
  _tags() {
    const byDevice = new Map();
    for (const entry of Object.values(this._hass.entities || {})) {
      if (entry.platform !== "plumio" || !entry.device_id) continue;
      const roles = { tag_location: "tracker", tag_room: "room", tag_battery: "battery", tag_last_seen: "seen" };
      const role = roles[entry.translation_key];
      if (!role) continue;
      const tag = byDevice.get(entry.device_id) || { device: entry.device_id };
      tag[role] = entry.entity_id;
      byDevice.set(entry.device_id, tag);
    }
    return [...byDevice.values()]
      .filter((tag) => tag.tracker)
      .map((tag) => {
        const device = this._hass.devices?.[tag.device] || {};
        const tracker = this._hass.states[tag.tracker];
        const room = tag.room ? this._hass.states[tag.room]?.state : undefined;
        const volts = tag.battery ? parseFloat(this._hass.states[tag.battery]?.state) : NaN;
        return {
          ...tag,
          name: device.name_by_user || device.name || tracker?.attributes.friendly_name || tag.tracker,
          icon: ICONS[tracker?.attributes.icon_key] || "mdi:tag",
          zone: tracker?.state,
          room: room && !NO_ROOM.has(room.toLowerCase()) ? room : null,
          seen: tracker?.attributes.last_seen || (tag.seen ? this._hass.states[tag.seen]?.state : null),
          low: !Number.isNaN(volts) && volts > 0 && volts < LOW_BATTERY_V,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  _ago(iso) {
    const time = Date.parse(iso || "");
    if (Number.isNaN(time)) return "";
    const seconds = Math.round((time - Date.now()) / 1000);
    if (seconds > -60) return this._t.now;
    const rtf = new Intl.RelativeTimeFormat(this._hass.locale?.language, { numeric: "auto" });
    for (const [unit, size] of [
      ["day", 86400],
      ["hour", 3600],
      ["minute", 60],
    ]) {
      if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
    }
    return this._t.now;
  }

  _zone(state) {
    if (!state || state === "unknown" || state === "unavailable") return this._t.nowhere;
    if (state === "not_home") return this._t.away;
    return this._hass.states[`zone.${state}`]?.attributes.friendly_name || state;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const tags = this._tags();
    // Every state change in the house reaches a card: redraw only when ours change.
    const signature = JSON.stringify([this._config, this._hass.locale?.language, tags]);
    if (signature === this._signature) return;
    this._signature = signature;

    const t = this._t;
    const rooms = new Map();
    const homeNoRoom = [];
    const away = [];
    for (const tag of tags) {
      if (tag.room) {
        if (!rooms.has(tag.room)) rooms.set(tag.room, []);
        rooms.get(tag.room).push(tag);
      } else if (tag.zone === "home") {
        homeNoRoom.push(tag);
      } else {
        away.push(tag);
      }
    }

    const row = (tag, detail) => `
      <div class="tag" data-entity="${escape(tag.tracker)}" tabindex="0" role="button">
        <ha-icon icon="${escape(tag.icon)}"></ha-icon>
        <div class="text">
          <div class="name">${escape(tag.name)}</div>
          <div class="detail">${escape(detail)}</div>
        </div>
        ${tag.low ? `<ha-icon class="low" icon="mdi:battery-alert-variant-outline" title="${escape(t.battery_low)}"></ha-icon>` : ""}
      </div>`;
    const group = (title, icon, list, detail) =>
      list.length
        ? `<section>
            <h3><ha-icon icon="${icon}"></ha-icon>${escape(title)}<span class="count">${list.length}</span></h3>
            ${list.map((tag) => row(tag, detail(tag))).join("")}
          </section>`
        : "";

    const sections = [
      ...[...rooms.keys()]
        .sort((a, b) => a.localeCompare(b))
        .map((room) => group(room, "mdi:door", rooms.get(room), (tag) => this._ago(tag.seen))),
      group(t.home_unknown_room, "mdi:home", homeNoRoom, (tag) => this._ago(tag.seen)),
      this._config.show_away
        ? group(t.away, "mdi:map-marker-outline", away, (tag) =>
            [this._zone(tag.zone), this._ago(tag.seen)].filter(Boolean).join(" · ")
          )
        : "",
    ].join("");

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 16px 8px; }
        h2 { margin: 4px 0 8px; font-size: 1.2em; font-weight: 500; }
        section { margin-bottom: 10px; }
        h3 { display: flex; align-items: center; gap: 8px; margin: 8px 0 4px; font-size: 0.95em;
             font-weight: 500; color: var(--secondary-text-color); }
        h3 ha-icon { --mdc-icon-size: 18px; }
        .count { margin-left: auto; font-size: 0.85em; }
        .tag { display: flex; align-items: center; gap: 12px; padding: 6px 4px; border-radius: 8px; cursor: pointer; }
        .tag:hover, .tag:focus-visible { background: var(--secondary-background-color); outline: none; }
        .tag > ha-icon { color: var(--state-icon-color, var(--primary-color)); }
        .text { flex: 1; min-width: 0; }
        .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .detail { font-size: 0.85em; color: var(--secondary-text-color); }
        .low { color: var(--warning-color, #ff9800); }
        .empty { color: var(--secondary-text-color); padding: 8px 0; }
      </style>
      <ha-card>
        ${this._config.title ? `<h2>${escape(this._config.title)}</h2>` : ""}
        ${tags.length ? sections : `<div class="empty">${escape(t.none)}</div>`}
      </ha-card>`;

    for (const el of this.shadowRoot.querySelectorAll(".tag")) {
      const open = () =>
        this.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId: el.dataset.entity }, bubbles: true, composed: true })
        );
      el.addEventListener("click", open);
      el.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && open());
    }
  }
}

if (!customElements.get("plumio-tags-card")) {
  customElements.define("plumio-tags-card", PlumioTagsCard);
  const t = textFor(document.querySelector("home-assistant")?.hass?.locale?.language || navigator.language);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "plumio-tags-card",
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://www.useplumio.com/home-assistant",
  });
}
