import { describe, it, expect } from "vitest";
import { searchSections, searchTotal } from "../../src/frontend/src/lib/searchResults.js";

const tr6 = {
  id: 119,
  category: "instrument",
  display_nr: "TR-0006",
  label: "Trompete YTR-935",
  manufacturer: "Yamaha",
  notes: "Belegliste nennt Lackinger Markus",
  active_loan: { musician_name: "Luisa Auinger", start_date: "2026-09-18", due_date: "2020-01-01" },
};
const result = {
  query: "markus",
  exact: null,
  items: [
    { category: "instrument", label: "Instrumente", total: 4, hits: [tr6] },
    { category: "clothing", label: "Kleidung", total: 1, hits: [{ ...tr6, id: 5, category: "clothing", display_nr: "K-0001", label: "Hut", active_loan: null, notes: null }] },
  ],
  musicians: { total: 1, hits: [{ id: 71, first_name: "Markus", last_name: "Lackinger", city: "Linz", is_active: false, is_extern: true }] },
  invoices: { total: 1, hits: [{ id: 3, title: "Reparatur", invoice_issuer: "Musikhaus", date_issued: "2026-02-01", amount: 120, currency: "€", item_id: 119, item_category: "instrument", item_display_nr: "TR-0006", item_label: "Trompete" }] },
};

describe("searchSections", () => {
  it("keeps the fixed order and builds links to the detail pages and lists", () => {
    const sections = searchSections(result);
    expect(sections.map((s) => s.label)).toEqual(["Instrumente", "Kleidung", "Musiker", "Rechnungen"]);
    const [instruments, clothing, musicians, invoices] = sections;
    expect(instruments.entries[0].to).toBe("/instrumente/TR-0006");
    expect(instruments.listTo).toBe("/instrumente?search=markus&bestand=alle");
    expect(clothing.entries[0].to).toBe("/kleidung/K-0001");
    expect(musicians.entries[0]).toMatchObject({ to: "/musiker/71", title: "Markus Lackinger", badges: ["inaktiv", "extern"], muted: true });
    expect(musicians.listTo).toBe("/musiker?search=markus&is_active=alle");
    expect(invoices.entries[0].to).toBe("/instrumente/TR-0006");
    expect(invoices.entries[0].context).toBe("TR-0006 Trompete");
  });

  it("shows the loan status, the borrower and where a hidden hit was found", () => {
    const entry = searchSections(result)[0].entries[0];
    expect(entry.status.label).toBe("Überfällig");
    expect(entry.borrower).toBe("Luisa Auinger");
    expect(entry.hint.label).toBe("Notizen");
    expect(searchSections(result)[1].entries[0].status.label).toBe("Verfügbar");
  });

  it("puts an exact inventory number first and doesn't repeat it", () => {
    const exact = searchSections({ ...result, query: "tr 6", exact: tr6 });
    expect(exact[0].label).toBe("Inventarnummer");
    expect(exact[0].entries[0].to).toBe("/instrumente/TR-0006");
    expect(exact.find((s) => s.key === "instrument")).toBeUndefined();
  });

  it("counts all hits", () => {
    expect(searchTotal(result)).toBe(7);
    expect(searchTotal(null)).toBe(0);
    expect(searchSections(null)).toEqual([]);
  });
});
