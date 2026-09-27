// Menge (Stückzahl) eines Inventarstücks.
// Das Backend liefert `quantity` (Ganzzahl ≥ 1); fehlt der Wert, gilt 1.

const numberFormat = new Intl.NumberFormat("de-AT", { maximumFractionDigits: 0 });

/** Liefert die Menge als Ganzzahl ≥ 1; fehlende oder ungültige Werte zählen als 1. */
export function itemQuantity(item) {
  const q = Number(item?.quantity);
  return Number.isInteger(q) && q >= 1 ? q : 1;
}

/** Tabellenzelle: leer bei 1, sonst die Zahl (de-AT). */
export function quantityCell(item) {
  const q = itemQuantity(item);
  return q > 1 ? numberFormat.format(q) : "";
}

/** Kartentext: „3 Stück“ bei mehr als einem Stück, sonst leer. */
export function quantityLabel(item) {
  const q = itemQuantity(item);
  return q > 1 ? `${numberFormat.format(q)} Stück` : "";
}

/** Detailseite: immer ein Wert, z. B. „1 Stück“ oder „12 Stück“. */
export function quantityDetail(item) {
  return `${numberFormat.format(itemQuantity(item))} Stück`;
}

/** Ob in einer Liste mindestens ein Eintrag mehr als ein Stück hat. */
export function hasMultipleQuantities(items) {
  return (items || []).some((i) => itemQuantity(i) > 1);
}

/**
 * Prüft die Formulareingabe. Gibt eine Fehlermeldung zurück oder "" wenn gültig.
 * Leere Eingabe ist ungültig, damit nicht stillschweigend 1 gespeichert wird.
 */
export function validateQuantity(value) {
  if (value === "" || value === null || value === undefined) return "Pflichtfeld";
  const q = Number(value);
  if (!Number.isInteger(q)) return "Nur ganze Zahlen";
  if (q < 1) return "Mindestens 1";
  return "";
}
