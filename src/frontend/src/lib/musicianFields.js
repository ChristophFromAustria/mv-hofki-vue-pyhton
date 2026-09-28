/** Inline-editable fields of a musician. */
const same = (key) => ({ value: (m) => m[key] ?? null, toPatch: (v) => ({ [key]: v }) });

export function musicianFieldDefs(registers = []) {
  return {
    membership: [
      {
        key: "is_active",
        label: "Status",
        type: "bool",
        value: (m) => m.is_active !== false,
        toPatch: (v) => ({ is_active: v }),
      },
      {
        key: "registers",
        label: "Register",
        type: "multiselect",
        options: registers.map((r) => ({ value: r.id, label: r.label })),
        value: (m) => (m.registers || []).map((r) => r.id),
        toPatch: (v) => ({ register_ids: v }),
      },
      {
        key: "is_extern",
        label: "Extern",
        type: "bool",
        value: (m) => !!m.is_extern,
        toPatch: (v) => ({ is_extern: v }),
      },
      {
        key: "notes",
        label: "Notizen",
        type: "textarea",
        block: true,
        maxLength: 10000,
        ...same("notes"),
      },
    ],
    contact: [
      { key: "first_name", label: "Vorname", type: "text", required: true, ...same("first_name") },
      { key: "last_name", label: "Nachname", type: "text", required: true, ...same("last_name") },
      { key: "phone", label: "Telefon", type: "text", ...same("phone") },
      { key: "email", label: "E-Mail", type: "text", ...same("email") },
      { key: "street_address", label: "Adresse", type: "text", ...same("street_address") },
      {
        key: "postal_code",
        label: "PLZ",
        type: "number",
        min: 1000,
        max: 99999,
        ...same("postal_code"),
      },
      { key: "city", label: "Ort", type: "text", ...same("city") },
    ],
  };
}
