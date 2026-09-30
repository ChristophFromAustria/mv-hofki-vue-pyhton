/** Papierkorb wording shared by delete confirmations and the trash page. */

export const TRASH_NOTE = "Wiederherstellen ist dort 90 Tage lang möglich.";

export const TRASH_CONFIRM = "In den Papierkorb";

// Where a restored row lives, for "Öffnen" after restoring.
export function trashLink(entry) {
  switch (entry.kind) {
    case "item":
      return `/inventar/${entry.id}`;
    case "musician":
      return `/musiker/${entry.id}`;
    case "instrument_type":
      return "/einstellungen/instrumententypen";
    case "clothing_type":
      return "/einstellungen/kleidungstypen";
    case "register":
      return "/einstellungen/register";
    case "general_item_category":
      return "/einstellungen/kategorien";
    case "sheet_music_genre":
      return "/einstellungen/notengenres";
    case "currency":
      return "/einstellungen/waehrungen";
    default:
      return null;
  }
}
