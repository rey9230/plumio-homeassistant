/*
 * Plumio — day route card.
 *
 * Draws where one member of a Nest went on a given day: the route, each leg between two
 * stops, and the stops themselves. The data comes from Plumio (the `plumio.get_day_timeline`
 * action), not from Home Assistant's recorder, so it also covers the days before the Nest
 * was linked.
 *
 *   type: custom:plumio-route-card
 *   entity: device_tracker.camila
 */

const TEXT = {
  en: {
    name: "Plumio — Day route",
    description: "Where a member of your Nest went on a given day.",
    today: "Today",
    loading: "Loading the route…",
    empty: "No movement recorded this day.",
    pick: "Choose a Plumio member in the card's settings.",
    not_plumio: "This entity is not a Plumio member.",
    distance: "Distance",
    legs: "Trips",
    stops: "Stops",
    start: "Start",
    end: "End",
    still_there: "still there",
    somewhere: "On the way",
    previous: "Previous day",
    next: "Next day",
    entity: "Member",
    title: "Title (optional)",
  },
  es: {
    name: "Plumio — Ruta del día",
    description: "Por dónde anduvo un miembro de tu Nido en un día.",
    today: "Hoy",
    loading: "Cargando la ruta…",
    empty: "No hay movimiento registrado este día.",
    pick: "Elige un miembro de Plumio en los ajustes de la tarjeta.",
    not_plumio: "Esta entidad no es un miembro de Plumio.",
    distance: "Distancia",
    legs: "Viajes",
    stops: "Paradas",
    start: "Inicio",
    end: "Fin",
    still_there: "sigue ahí",
    somewhere: "En camino",
    previous: "Día anterior",
    next: "Día siguiente",
    entity: "Miembro",
    title: "Título (opcional)",
  },
  de: {
    name: "Plumio — Tagesroute",
    description: "Wo ein Mitglied deines Nests an einem Tag unterwegs war.",
    today: "Heute",
    loading: "Route wird geladen…",
    empty: "An diesem Tag wurde keine Bewegung aufgezeichnet.",
    pick: "Wähle in den Karteneinstellungen ein Plumio-Mitglied.",
    not_plumio: "Diese Entität ist kein Plumio-Mitglied.",
    distance: "Strecke",
    legs: "Fahrten",
    stops: "Aufenthalte",
    start: "Start",
    end: "Ende",
    still_there: "noch dort",
    somewhere: "Unterwegs",
    previous: "Vorheriger Tag",
    next: "Nächster Tag",
    entity: "Mitglied",
    title: "Titel (optional)",
  },
  fr: {
    name: "Plumio — Trajet du jour",
    description: "Où un membre de votre Nid s’est déplacé un jour donné.",
    today: "Aujourd’hui",
    loading: "Chargement du trajet…",
    empty: "Aucun déplacement enregistré ce jour-là.",
    pick: "Choisissez un membre Plumio dans les réglages de la carte.",
    not_plumio: "Cette entité n’est pas un membre Plumio.",
    distance: "Distance",
    legs: "Trajets",
    stops: "Arrêts",
    start: "Départ",
    end: "Arrivée",
    still_there: "toujours sur place",
    somewhere: "En route",
    previous: "Jour précédent",
    next: "Jour suivant",
    entity: "Membre",
    title: "Titre (facultatif)",
  },
  it: {
    name: "Plumio — Percorso del giorno",
    description: "Dove è stato un membro del tuo Nido in un dato giorno.",
    today: "Oggi",
    loading: "Caricamento del percorso…",
    empty: "Nessuno spostamento registrato in questo giorno.",
    pick: "Scegli un membro Plumio nelle impostazioni della scheda.",
    not_plumio: "Questa entità non è un membro Plumio.",
    distance: "Distanza",
    legs: "Viaggi",
    stops: "Soste",
    start: "Inizio",
    end: "Fine",
    still_there: "ancora lì",
    somewhere: "In viaggio",
    previous: "Giorno precedente",
    next: "Giorno successivo",
    entity: "Membro",
    title: "Titolo (facoltativo)",
  },
  pt: {
    name: "Plumio — Rota do dia",
    description: "Por onde um membro do seu Ninho andou em um dia.",
    today: "Hoje",
    loading: "Carregando a rota…",
    empty: "Nenhum movimento registrado neste dia.",
    pick: "Escolha um membro do Plumio nas configurações do cartão.",
    not_plumio: "Esta entidade não é um membro do Plumio.",
    distance: "Distância",
    legs: "Viagens",
    stops: "Paradas",
    start: "Início",
    end: "Fim",
    still_there: "ainda lá",
    somewhere: "A caminho",
    previous: "Dia anterior",
    next: "Dia seguinte",
    entity: "Membro",
    title: "Título (opcional)",
  },
  "zh-Hant": {
    name: "Plumio — 當日路線",
    description: "巢中某位成員在某一天去過哪些地方。",
    today: "今天",
    loading: "正在載入路線…",
    empty: "這一天沒有移動紀錄。",
    pick: "請在卡片設定中選擇一位 Plumio 成員。",
    not_plumio: "此實體不是 Plumio 成員。",
    distance: "距離",
    legs: "行程",
    stops: "停留",
    start: "起點",
    end: "終點",
    still_there: "仍在此處",
    somewhere: "途中",
    previous: "前一天",
    next: "後一天",
    entity: "成員",
    title: "標題（選填）",
  },
};

function textFor(language) {
  const lang = (language || "en").toLowerCase();
  if (lang.startsWith("zh")) return TEXT["zh-Hant"];
  return TEXT[lang.split("-")[0]] || TEXT.en;
}

const REFRESH_MS = 5 * 60 * 1000;
const SIMPLIFY_METERS = 25;

/** Douglas-Peucker over a short route: drops the points a straight line already covers. */
function simplify(points, toleranceMeters) {
  if (points.length < 3) return points;
  const lat0 = (points[0].lat * Math.PI) / 180;
  const xy = points.map((p) => [p.lng * 111320 * Math.cos(lat0), p.lat * 110540]);
  const keep = new Uint8Array(points.length);
  keep[0] = keep[points.length - 1] = 1;
  const stack = [[0, points.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, ay] = xy[a];
    const dx = xy[b][0] - ax;
    const dy = xy[b][1] - ay;
    const len2 = dx * dx + dy * dy;
    let worst = 0;
    let at = -1;
    for (let i = a + 1; i < b; i++) {
      const px = xy[i][0] - ax;
      const py = xy[i][1] - ay;
      const t = len2 ? Math.max(0, Math.min(1, (px * dx + py * dy) / len2)) : 0;
      const d = Math.hypot(px - t * dx, py - t * dy);
      if (d > worst) {
        worst = d;
        at = i;
      }
    }
    if (worst > toleranceMeters) {
      keep[at] = 1;
      stack.push([a, at], [at, b]);
    }
  }
  return points.filter((_, i) => keep[i]);
}
const DAY_MS = 24 * 60 * 60 * 1000;

class PlumioRouteCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { domain: "device_tracker", integration: "plumio" } } },
        { name: "title", selector: { text: {} } },
      ],
      computeLabel: (schema, localize) => {
        const lang = document.querySelector("home-assistant")?.hass?.locale?.language;
        return textFor(lang)[schema.name] || schema.name;
      },
    };
  }

  static getStubConfig(hass) {
    const first = Object.values(hass.entities || {}).find(
      (e) => e.platform === "plumio" && e.entity_id.startsWith("device_tracker.") && e.translation_key === "location"
    );
    return { entity: first ? first.entity_id : "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._day = null; // YYYY-MM-DD in Home Assistant's time zone
    this._data = null;
    this._error = null;
    this._loading = false;
    this._request = 0;
  }

  setConfig(config) {
    this._config = { ...config };
    this._built = false;
    if (this._hass) this._start();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._map) this._map.hass = hass;
    if (first && this._config) this._start();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  connectedCallback() {
    this._timer = setInterval(() => {
      if (this._day === this._today()) this._load();
    }, REFRESH_MS);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  // ---------- dates, in Home Assistant's time zone ----------

  get _t() {
    return textFor(this._hass?.locale?.language);
  }

  _ymd(date) {
    return new Intl.DateTimeFormat("en-CA", { timeZone: this._hass.config.time_zone }).format(date);
  }

  _today() {
    return this._ymd(new Date());
  }

  _shift(days) {
    // Noon UTC keeps the arithmetic clear of any daylight-saving edge.
    const next = new Date(new Date(`${this._day}T12:00:00Z`).getTime() + days * DAY_MS);
    const ymd = next.toISOString().slice(0, 10);
    if (ymd > this._today()) return;
    this._day = ymd;
    this._load();
  }

  _dayLabel() {
    if (this._day === this._today()) return this._t.today;
    return new Intl.DateTimeFormat(this._hass.locale?.language, {
      weekday: "short",
      day: "numeric",
      month: "short",
      timeZone: "UTC",
    }).format(new Date(`${this._day}T12:00:00Z`));
  }

  _time(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat(this._hass.locale?.language, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: this._hass.config.time_zone,
    }).format(new Date(iso));
  }

  _distance(meters) {
    const imperial = this._hass.config.unit_system?.length === "mi";
    const value = imperial ? meters / 1609.344 : meters / 1000;
    const digits = value >= 100 ? 0 : 1;
    return `${new Intl.NumberFormat(this._hass.locale?.language, { maximumFractionDigits: digits }).format(value)} ${
      imperial ? "mi" : "km"
    }`;
  }

  _duration(seconds) {
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
  }

  // ---------- data ----------

  _start() {
    if (!this._day) this._day = this._today();
    this._build();
    this._load();
  }

  async _load() {
    const entityId = this._config.entity;
    if (!entityId) return this._show({ error: this._t.pick });
    const entry = this._hass.entities?.[entityId];
    if (!entry || entry.platform !== "plumio" || !entry.device_id) return this._show({ error: this._t.not_plumio });

    const request = ++this._request;
    this._loading = true;
    this._render();
    try {
      const result = await this._hass.callWS({
        type: "call_service",
        domain: "plumio",
        service: "get_day_timeline",
        service_data: { device_id: entry.device_id, date: this._day },
        return_response: true,
      });
      if (request !== this._request) return; // the person moved to another day meanwhile
      this._show({ data: result.response });
    } catch (err) {
      if (request !== this._request) return;
      this._show({ error: err?.message || String(err) });
    }
  }

  _show({ data = null, error = null }) {
    this._data = data;
    this._error = error;
    this._loading = false;
    this._render();
    this._draw();
  }

  // ---------- layout ----------

  _build() {
    if (this._built) return;
    this._built = true;
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; display: flex; flex-direction: column; }
        .head { display: flex; align-items: center; gap: 8px; padding: 12px 8px 8px 16px; }
        .title { flex: 1; min-width: 0; font-size: 1.15rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .day { min-width: 6.5em; text-align: center; color: var(--secondary-text-color); font-size: 0.95rem; }
        button.nav { border: 0; background: none; color: var(--primary-text-color); cursor: pointer; width: 36px; height: 36px; border-radius: 50%; font-size: 20px; line-height: 1; }
        button.nav:hover:not([disabled]) { background: var(--secondary-background-color); }
        button.nav[disabled] { opacity: 0.3; cursor: default; }
        .map { position: relative; height: 300px; flex: none; }
        ha-map { height: 100%; width: 100%; }
        .veil { position: absolute; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 24px; text-align: center; background: color-mix(in srgb, var(--card-background-color) 82%, transparent); color: var(--primary-text-color); }
        .veil.error { color: var(--error-color); }
        .veil[hidden] { display: none; }
        .stats { display: flex; gap: 24px; padding: 12px 16px 4px; }
        .stat b { display: block; font-size: 1.25rem; font-weight: 500; }
        .stat span { color: var(--secondary-text-color); font-size: 0.85rem; }
        ol { list-style: none; margin: 0; padding: 4px 16px 14px; max-height: 264px; overflow-y: auto; }
        li { display: grid; grid-template-columns: 14px 1fr auto; gap: 10px; align-items: baseline; padding: 6px 0; border-top: 1px solid var(--divider-color); }
        li:first-child { border-top: 0; }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--primary-color); align-self: center; }
        .dot.leg { border-radius: 2px; height: 4px; }
        .what { min-width: 0; }
        .what small { display: block; color: var(--secondary-text-color); }
        .when { color: var(--secondary-text-color); font-size: 0.9rem; white-space: nowrap; }
      </style>
      <ha-card>
        <div class="head">
          <div class="title"></div>
          <button class="nav prev" aria-label="">‹</button>
          <div class="day"></div>
          <button class="nav next" aria-label="">›</button>
        </div>
        <div class="map"><div class="veil" hidden></div></div>
        <div class="stats"></div>
        <ol></ol>
      </ha-card>`;
    this.shadowRoot.querySelector(".prev").addEventListener("click", () => this._shift(-1));
    this.shadowRoot.querySelector(".next").addEventListener("click", () => this._shift(1));
    this._mountMap();
  }

  async _mountMap() {
    // `ha-map` is loaded lazily by Home Assistant, with the built-in map card.
    if (!customElements.get("ha-map")) {
      const helpers = await window.loadCardHelpers();
      helpers.createCardElement({ type: "map", entities: [] });
      await customElements.whenDefined("ha-map");
    }
    const map = document.createElement("ha-map");
    map.hass = this._hass;
    map.entities = [];
    map.paths = [];
    map.autoFit = false;
    map.renderPassive = false;
    map.interactiveZones = false;
    this.shadowRoot.querySelector(".map").prepend(map);
    this._map = map;
    this._draw();
  }

  _render() {
    if (!this._built) return;
    const t = this._t;
    const root = this.shadowRoot;
    const state = this._hass.states[this._config.entity];
    root.querySelector(".title").textContent =
      this._config.title || this._data?.displayName || state?.attributes?.friendly_name || "Plumio";
    root.querySelector(".day").textContent = this._dayLabel();
    const prev = root.querySelector(".prev");
    const next = root.querySelector(".next");
    prev.setAttribute("aria-label", t.previous);
    next.setAttribute("aria-label", t.next);
    next.disabled = this._day >= this._today();

    const veil = root.querySelector(".veil");
    const data = this._data;
    const empty = data && !(data.route || []).length && !(data.stays || []).length;
    const message = this._error || (this._loading && !data ? t.loading : empty ? t.empty : "");
    veil.hidden = !message;
    veil.textContent = message;
    veil.classList.toggle("error", Boolean(this._error));

    const stats = root.querySelector(".stats");
    const list = root.querySelector("ol");
    stats.replaceChildren();
    list.replaceChildren();
    if (!data || this._error) return;

    const legs = data.legs || [];
    const stays = data.stays || [];
    for (const [value, label] of [
      [this._distance(data.distanceMeters || 0), t.distance],
      [String(legs.length), t.legs],
      [String(stays.length), t.stops],
    ]) {
      const stat = document.createElement("div");
      stat.className = "stat";
      stat.append(Object.assign(document.createElement("b"), { textContent: value }));
      stat.append(Object.assign(document.createElement("span"), { textContent: label }));
      stats.append(stat);
    }

    // One list, in the order things happened: a stop, the trip after it, the next stop…
    const rows = [
      ...stays.map((s) => ({
        at: s.arrivalAt,
        leg: false,
        title: s.placeName,
        detail: this._duration(s.durationSeconds || 0),
        when: `${this._time(s.arrivalAt)} – ${s.departureAt ? this._time(s.departureAt) : t.still_there}`,
      })),
      ...legs.map((l) => ({
        at: l.startedAt,
        leg: true,
        title: `${l.fromName || t.somewhere} → ${l.toName || t.somewhere}`,
        detail: this._distance(l.distanceMeters || 0),
        when: `${this._time(l.startedAt)} – ${this._time(l.endedAt)}`,
      })),
    ].sort((a, b) => new Date(a.at) - new Date(b.at));

    for (const row of rows) {
      const li = document.createElement("li");
      const dot = Object.assign(document.createElement("span"), { className: row.leg ? "dot leg" : "dot" });
      const what = Object.assign(document.createElement("div"), { className: "what", textContent: row.title });
      what.append(Object.assign(document.createElement("small"), { textContent: row.detail }));
      const when = Object.assign(document.createElement("div"), { className: "when", textContent: row.when });
      li.append(dot, what, when);
      list.append(li);
    }
  }

  // ---------- map ----------

  /**
   * Only through what `ha-map` offers in public — `paths` and `fitBounds` — and never by
   * reaching for the map engine underneath: Home Assistant changed it (Leaflet to
   * MapLibre) and a card drawing on the engine itself would have gone blank.
   */
  _draw() {
    const map = this._map;
    if (!map) return;
    const data = this._data;
    if (!data || this._error) {
      map.paths = [];
      return;
    }

    const style = getComputedStyle(this);
    const line = style.getPropertyValue("--primary-color").trim() || "#03a9f4";
    const stop = style.getPropertyValue("--accent-color").trim() || "#ff9800";
    const fallback = data.fromTs || `${this._day}T12:00:00Z`;
    const paths = [];
    const bounds = [];

    // `ha-map` puts a dot on every point of a path. On a straight road that is hundreds of
    // dots fused into a fat line, so only the points that bend the route are kept.
    const route = simplify(data.route || [], SIMPLIFY_METERS).map((p) => ({
      point: [p.lat, p.lng],
      timestamp: new Date(p.ts || fallback),
    }));
    if (route.length) {
      paths.push({ name: data.displayName || "", color: line, points: route });
      bounds.push(...route.map((p) => p.point));
    }
    // A stop is a path of one point: a marker with the place's name and when they got there.
    for (const stay of data.stays || []) {
      if (stay.lat == null || stay.lng == null) continue;
      const point = [stay.lat, stay.lng];
      paths.push({ name: stay.placeName, color: stop, points: [{ point, timestamp: new Date(stay.arrivalAt) }] });
      bounds.push(point);
    }

    map.paths = paths;
    if (bounds.length && typeof map.fitBounds === "function") map.fitBounds(bounds, { pad: 0.2, zoom: 16 });
  }
}

if (!customElements.get("plumio-route-card")) {
  customElements.define("plumio-route-card", PlumioRouteCard);
  const t = textFor(document.querySelector("home-assistant")?.hass?.locale?.language || navigator.language);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "plumio-route-card",
    name: t.name,
    description: t.description,
    preview: false,
    documentationURL: "https://www.useplumio.com/home-assistant",
  });
}
