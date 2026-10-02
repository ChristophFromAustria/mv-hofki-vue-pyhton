/** Wording and links for event log entries (GET /events). */

export const ACTION_LABELS = {
  created: "angelegt",
  updated: "geändert",
  deleted: "gelöscht",
  loaned: "ausgeliehen",
  returned: "zurückgegeben",
  image_added: "Bild hinzugefügt",
  image_deleted: "Bild gelöscht",
  image_profile: "Profilbild gesetzt",
  image_edited: "Bild bearbeitet",
  image_original: "Bild-Original wiederhergestellt",
  imported: "importiert",
  wiped: "Bestand geleert",
  trashed: "in den Papierkorb",
  restored: "wiederhergestellt",
  purged: "endgültig gelöscht",
  retired: "ausgeschieden",
  reinstated: "wieder in Bestand",
};

export const ENTITY_LABELS = {
  item: "Gegenstand",
  musician: "Musiker",
  loan: "Leihe",
  invoice: "Rechnung",
  image: "Bild",
  instrument_type: "Instrumententyp",
  clothing_type: "Kleidungstyp",
  register: "Register",
  general_item_category: "Kategorie",
  sheet_music_genre: "Gattung",
  currency: "Währung",
  import: "Import",
};

// Filter choices of the Protokoll page (backend: filters/event.py AREAS).
export const AREA_OPTIONS = [
  { value: "item", label: "Inventar" },
  { value: "musician", label: "Musiker" },
  { value: "loan", label: "Leihen" },
  { value: "invoice", label: "Rechnungen" },
  { value: "master_data", label: "Stammdaten" },
  { value: "import", label: "Importe" },
];

export const ACTION_OPTIONS = Object.entries(ACTION_LABELS).map(([value, label]) => ({
  value,
  label: label[0].toUpperCase() + label.slice(1),
}));

const SOURCE_LABELS = { "ki-import": "KI-Import", import: "Inventar-Import", system: "System" };

const MASTER_DATA_ROUTES = {
  instrument_type: "/einstellungen/instrumententypen",
  clothing_type: "/einstellungen/kleidungstypen",
  register: "/einstellungen/register",
  general_item_category: "/einstellungen/kategorien",
  sheet_music_genre: "/einstellungen/notengenres",
  currency: "/einstellungen/waehrungen",
};

/** Who did it: the e-mail, else where it came from, else "unbekannt". */
export function actorLabel(event) {
  if (event.actor) return event.actor;
  return SOURCE_LABELS[event.source] || "unbekannt";
}

/** "30.09.2026, 14:02" in local time (events are stored in UTC). */
export function formatEventTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("de-AT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Where the event's record lives, or null (deleted records have no page). */
export function eventLink(event) {
  if (event.action === "deleted" || event.action === "purged") return null;
  if (event.entity_type === "musician") return `/musiker/${event.entity_id}`;
  if (MASTER_DATA_ROUTES[event.entity_type]) return MASTER_DATA_ROUTES[event.entity_type];
  if (event.item_id != null) return `/inventar/${event.item_id}`;
  if (event.musician_id != null) return `/musiker/${event.musician_id}`;
  return null;
}

/** "Gegenstand geändert", "Leihe ausgeliehen" … as the headline of an entry. */
export function eventHeadline(event) {
  const what = ENTITY_LABELS[event.entity_type] || event.entity_type;
  const action = ACTION_LABELS[event.action] || event.action;
  // "Ausgeliehen" / "Zurückgegeben" say it all; other loan events name it.
  if (event.entity_type === "loan" && ["loaned", "returned"].includes(event.action)) {
    return action[0].toUpperCase() + action.slice(1);
  }
  return `${what} ${action}`;
}

// Long texts are shown shortened; the full value is in the title attribute.
const LONG = 80;

/** Changes as [{ label, old, new, long }] with "—" for empty values. */
export function eventChanges(event) {
  return (event.changes || []).map((c) => {
    const old = c.old == null || c.old === "" ? "—" : String(c.old);
    const now = c.new == null || c.new === "" ? "—" : String(c.new);
    return {
      label: c.label,
      old,
      new: now,
      oldEmpty: old === "—",
      long: old.length > LONG || now.length > LONG,
    };
  });
}

export function shorten(text, max = LONG) {
  const flat = String(text).replace(/\s+/g, " ");
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}
