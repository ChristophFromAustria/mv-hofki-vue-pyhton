export const SESSION_STATUS = {
  uploaded: { label: "Hochgeladen", badge: "badge-gray" },
  analyzing: { label: "Analyse läuft", badge: "badge-blue" },
  review: { label: "Zur Prüfung", badge: "badge-warning" },
  importing: { label: "Import läuft", badge: "badge-blue" },
  imported: { label: "Importiert", badge: "badge-success" },
  error: { label: "Fehler", badge: "badge-danger" },
};

export const PAGE_STATUS = {
  uploaded: { label: "Offen", badge: "badge-gray" },
  analyzing: { label: "Läuft", badge: "badge-blue" },
  done: { label: "Fertig", badge: "badge-success" },
  error: { label: "Fehler", badge: "badge-danger" },
};

export function sessionStatus(status) {
  return SESSION_STATUS[status] || { label: status, badge: "badge-gray" };
}

export function pageStatus(status) {
  return PAGE_STATUS[status] || { label: status, badge: "badge-gray" };
}

const dateFormat = new Intl.DateTimeFormat("de-AT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(value) {
  if (!value) return "";
  return dateFormat.format(new Date(value));
}
