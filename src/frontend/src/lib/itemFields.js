/** Inline-editable master-data fields of an item, per kind. */

const opt = (rows) => rows.map((r) => ({ value: r.id, label: r.label }));
const same = (key) => ({ value: (item) => item[key] ?? null, toPatch: (v) => ({ [key]: v }) });

const COMMON_TAIL = [
  { key: "manufacturer", label: "Hersteller", type: "text", ...same("manufacturer") },
  { key: "owner", label: "Eigentümer", type: "text", required: true, ...same("owner") },
  {
    key: "acquisition_date",
    label: "Anschaffungsdatum",
    type: "date",
    ...same("acquisition_date"),
  },
  {
    key: "acquisition_cost",
    label: "Anschaffungskosten",
    type: "money",
    value: (item) => ({
      amount: item.acquisition_cost ?? null,
      currency_id: item.currency_id ?? null,
    }),
    toPatch: (v) => ({ acquisition_cost: v.amount, currency_id: v.currency_id }),
  },
  { key: "notes", label: "Notizen", type: "textarea", ...same("notes") },
];

const QUANTITY = {
  key: "quantity",
  label: "Menge",
  type: "number",
  required: true,
  min: 1,
  ...same("quantity"),
};

function typeField(idField, types) {
  return {
    key: "type",
    label: "Typ",
    type: "select",
    required: true,
    options: opt(types),
    value: (item) => item[idField] ?? null,
    toPatch: (v) => ({ [idField]: v, label: types.find((t) => t.id === v)?.label }),
  };
}

export function itemFieldDefs(category, { types = [], genres = [], categories = [] } = {}) {
  const withoutManufacturer = COMMON_TAIL.filter((f) => f.key !== "manufacturer");
  switch (category) {
    case "instrument":
      return [
        typeField("instrument_type_id", types),
        QUANTITY,
        { key: "serial_nr", label: "Seriennummer", type: "text", ...same("serial_nr") },
        { key: "manufacturer", label: "Hersteller", type: "text", ...same("manufacturer") },
        {
          key: "construction_year",
          label: "Baujahr",
          type: "number",
          min: 1800,
          max: new Date().getFullYear() + 1,
          ...same("construction_year"),
        },
        { key: "distributor", label: "Händler", type: "text", ...same("distributor") },
        { key: "container", label: "Behältnis", type: "text", ...same("container") },
        {
          key: "particularities",
          label: "Besonderheiten",
          type: "textarea",
          ...same("particularities"),
        },
        ...withoutManufacturer,
      ];
    case "clothing":
      return [
        typeField("clothing_type_id", types),
        QUANTITY,
        { key: "size", label: "Größe", type: "text", ...same("size") },
        { key: "gender", label: "Geschlecht", type: "text", ...same("gender") },
        ...COMMON_TAIL,
      ];
    case "sheet_music":
      return [
        { key: "label", label: "Titel", type: "text", required: true, ...same("label") },
        QUANTITY,
        { key: "composer", label: "Komponist", type: "text", ...same("composer") },
        { key: "arranger", label: "Arrangeur", type: "text", ...same("arranger") },
        { key: "difficulty", label: "Schwierigkeitsgrad", type: "text", ...same("difficulty") },
        {
          key: "genre",
          label: "Gattung",
          type: "select",
          options: opt(genres),
          value: (item) => item.genre_id ?? null,
          toPatch: (v) => ({ genre_id: v }),
        },
        { key: "storage_location", label: "Lagerort", type: "text", ...same("storage_location") },
        ...COMMON_TAIL,
      ];
    default:
      return [
        { key: "label", label: "Bezeichnung", type: "text", required: true, ...same("label") },
        QUANTITY,
        {
          key: "categories",
          label: "Kategorien",
          type: "tags",
          options: opt(categories),
          value: (item) => (item.categories || []).map((c) => c.id),
          toPatch: (v) => ({ category_ids: v }),
        },
        { key: "storage_location", label: "Lagerort", type: "text", ...same("storage_location") },
        ...COMMON_TAIL,
      ];
  }
}

export function renumberPrefix(item, newTypeId, types) {
  if (item.category !== "instrument") return null;
  const current = item.number_prefix ?? String(item.display_nr || "").split("-")[0];
  const next = types
    .find((t) => t.id === newTypeId)
    ?.label_short?.trim()
    .toUpperCase();
  return next && next !== current ? next : null;
}
