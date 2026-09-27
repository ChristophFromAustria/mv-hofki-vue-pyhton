import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import DataTable from "../../src/frontend/src/components/DataTable.vue";

const columns = [
  { key: "display_nr", label: "Nr.", sortKey: "number" },
  { key: "label", label: "Bezeichnung" },
  { key: "year", label: "Baujahr", sortKey: "construction_year" },
];
const rows = [{ id: 1, display_nr: "A-001", label: "Tisch", year: 1990 }];

describe("DataTable sorting", () => {
  it("marks the active column and toggles direction", async () => {
    const w = mount(DataTable, { props: { columns, rows, sort: "number" } });
    const ths = w.findAll("th");
    expect(ths[0].attributes("aria-sort")).toBe("ascending");
    expect(ths[1].attributes("aria-sort")).toBeUndefined();
    expect(ths[2].attributes("aria-sort")).toBe("none");
    await ths[0].find("button").trigger("click");
    await ths[2].find("button").trigger("click");
    expect(w.emitted("update:sort")).toEqual([["-number"], ["construction_year"]]);
  });

  it("uses the empty text", () => {
    const w = mount(DataTable, {
      props: { columns, rows: [], emptyText: "Keine Einträge für diese Filter." },
    });
    expect(w.text()).toContain("Keine Einträge für diese Filter.");
  });
});
