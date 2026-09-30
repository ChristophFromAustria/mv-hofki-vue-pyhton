/** Turn a GET /search result into ordered sections of entries (popup + page). */
import { CATEGORIES } from "./categories.js";
import { formatDate, formatMoney } from "./format.js";
import { searchHint } from "./highlight.js";
import { loanStatus } from "./loans.js";

// ItemHit fields shown in an entry; a hit elsewhere (notes) gets a hint.
const ITEM_VISIBLE = ["label", "display_nr", "manufacturer", "borrower"];

function itemEntry(hit, term) {
  const cat = CATEGORIES[hit.category];
  const loan = hit.active_loan;
  const row = { ...hit, borrower: loan?.musician_name || "" };
  return {
    key: `item-${hit.id}`,
    kind: "item",
    to: `${cat?.routeBase || "/instrumente"}/${hit.id}`,
    title: hit.label,
    displayNr: hit.display_nr,
    meta: hit.manufacturer || "",
    borrower: row.borrower,
    status: loan
      ? loanStatus({ ...loan, end_date: null })
      : { label: "Verfügbar", badge: "badge badge-gray" },
    hint: searchHint(row, term, ITEM_VISIBLE),
    image: hit.profile_image_url,
  };
}

function musicianEntry(hit) {
  const badges = [];
  if (!hit.is_active) badges.push("inaktiv");
  if (hit.is_extern) badges.push("extern");
  return {
    key: `musician-${hit.id}`,
    kind: "musician",
    to: `/musiker/${hit.id}`,
    title: `${hit.first_name} ${hit.last_name}`,
    meta: [hit.city, hit.email].filter(Boolean).join(" · "),
    badges,
    muted: !hit.is_active,
  };
}

function invoiceEntry(hit) {
  const cat = CATEGORIES[hit.item_category];
  return {
    key: `invoice-${hit.id}`,
    kind: "invoice",
    to: `${cat?.routeBase || "/instrumente"}/${hit.item_id}`,
    title: hit.title,
    meta: [
      hit.invoice_issuer,
      formatDate(hit.date_issued),
      formatMoney(hit.amount, hit.currency || ""),
    ]
      .filter(Boolean)
      .join(" · "),
    context: `${hit.item_display_nr} ${hit.item_label}`,
  };
}

/**
 * [{ key, label, total, listTo, entries }] in the fixed order: exact
 * inventory number, item categories, musicians, invoices. `listTo` opens the
 * matching list filtered by the term (for "all hits").
 */
export function searchSections(result, term = result?.query || "") {
  if (!result) return [];
  const sections = [];
  const q = encodeURIComponent(term);
  if (result.exact) {
    sections.push({
      key: "exact",
      label: "Inventarnummer",
      total: 1,
      entries: [itemEntry(result.exact, term)],
    });
  }
  for (const group of result.items || []) {
    const cat = CATEGORIES[group.category];
    sections.push({
      key: group.category,
      label: group.label,
      total: group.total,
      listTo: cat ? `${cat.routeBase}?search=${q}` : null,
      entries: group.hits.filter((h) => h.id !== result.exact?.id).map((h) => itemEntry(h, term)),
    });
  }
  if (result.musicians?.total) {
    sections.push({
      key: "musicians",
      label: "Musiker",
      total: result.musicians.total,
      listTo: `/musiker?search=${q}&is_active=alle`,
      entries: result.musicians.hits.map(musicianEntry),
    });
  }
  if (result.invoices?.total) {
    sections.push({
      key: "invoices",
      label: "Rechnungen",
      total: result.invoices.total,
      listTo: `/rechnungen?search=${q}`,
      entries: result.invoices.hits.map(invoiceEntry),
    });
  }
  return sections.filter((s) => s.entries.length);
}

/** Number of hits over all sections (the exact number counts once). */
export function searchTotal(result) {
  if (!result) return 0;
  const items = (result.items || []).reduce((n, g) => n + g.total, 0);
  return items + (result.musicians?.total || 0) + (result.invoices?.total || 0);
}
