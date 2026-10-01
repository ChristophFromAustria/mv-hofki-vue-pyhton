/**
 * "Kopieren": which values of an item can be taken over into new items.
 * Values that belong to one piece only (serial number, notes,
 * particularities) are off by default; the type is always taken over — it
 * decides the number sequence. The copy always gets a new number.
 */

const COMMON = [
  { key: "quantity", label: "Menge", fields: ["quantity"], on: true },
  { key: "manufacturer", label: "Hersteller", fields: ["manufacturer"], on: true },
  { key: "owner", label: "Eigentümer", fields: ["owner"], on: true },
  {
    key: "acquisition",
    label: "Anschaffung (Datum, Kosten, Währung)",
    fields: ["acquisition_date", "acquisition_cost", "currency_id"],
    on: true,
  },
  { key: "storage_location", label: "Lagerort", fields: ["storage_location"], on: true },
];

const BY_CATEGORY = {
  instrument: [
    { key: "type", label: "Typ", fields: ["instrument_type_id"], on: true, locked: true },
    ...COMMON,
    { key: "construction_year", label: "Baujahr", fields: ["construction_year"], on: true },
    { key: "distributor", label: "Händler", fields: ["distributor"], on: true },
    { key: "container", label: "Behältnis", fields: ["container"], on: true },
    { key: "serial_nr", label: "Seriennummer", fields: ["serial_nr"], on: false },
    { key: "particularities", label: "Besonderheiten", fields: ["particularities"], on: false },
  ],
  clothing: [
    { key: "type", label: "Typ", fields: ["clothing_type_id"], on: true, locked: true },
    ...COMMON,
    { key: "size", label: "Größe", fields: ["size"], on: true },
    { key: "gender", label: "Geschlecht", fields: ["gender"], on: true },
  ],
  sheet_music: [
    ...COMMON,
    { key: "composer", label: "Komponist", fields: ["composer"], on: true },
    { key: "arranger", label: "Arrangeur", fields: ["arranger"], on: true },
    { key: "difficulty", label: "Schwierigkeitsgrad", fields: ["difficulty"], on: true },
    { key: "genre", label: "Gattung", fields: ["genre_id"], on: true },
  ],
  general_item: [
    ...COMMON,
    { key: "categories", label: "Kategorien", fields: ["category_ids"], on: true },
  ],
};
// Notes last for every category.
const NOTES = { key: "notes", label: "Notizen", fields: ["notes"], on: false };

export const MAX_COPIES = 20;

function valueOf(item, field) {
  if (field === "category_ids") return (item.categories || []).map((c) => c.id);
  return item[field];
}

function hasValue(value) {
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && value !== undefined && value !== "";
}

/** The choices for this item: only fields that have a value (and the type). */
export function copyChoices(item, category) {
  return [...(BY_CATEGORY[category] || COMMON), NOTES].filter(
    (c) => c.locked || c.fields.some((f) => hasValue(valueOf(item, f))),
  );
}

/** Keys of the choices that are on by default. */
export function defaultCopyKeys(choices) {
  return choices.filter((c) => c.on).map((c) => c.key);
}

/** The POST /items body for one copy. */
export function copyPayload(item, category, chosenKeys, label) {
  const payload = { category, label };
  for (const choice of copyChoices(item, category)) {
    if (!choice.locked && !chosenKeys.includes(choice.key)) continue;
    for (const field of choice.fields) {
      const value = valueOf(item, field);
      if (hasValue(value)) payload[field] = value;
    }
  }
  return payload;
}
