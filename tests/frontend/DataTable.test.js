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

describe("DataTable groups and selection", () => {
  const cols = [{ key: "label", label: "Bezeichnung" }];
  const grows = [
    { id: 1, _key: "a:1", group_key: "a", label: "Eins" },
    { id: 2, _key: "b:2", group_key: "b", label: "Zwei" },
    { id: 1, _key: "b:1", group_key: "b", label: "Eins" },
  ];
  const groups = [
    { key: "a", label: "Alpha", count: 1 },
    { key: "b", label: "Beta", count: 2 },
  ];

  it("renders group rows with rowgroup headers and hides collapsed rows", async () => {
    const w = mount(DataTable, { props: { columns: cols, rows: grows, groups, collapsedGroups: new Set(["a"]) } });
    const headers = w.findAll('th[scope="rowgroup"]');
    expect(headers.map((h) => h.text())).toEqual([expect.stringContaining("Alpha"), expect.stringContaining("Beta")]);
    expect(w.findAll("tbody tr td").map((td) => td.text())).toEqual(["Zwei", "Eins"]);
    await headers[1].find("button").trigger("click");
    expect(w.emitted("toggle-group")).toEqual([["b"]]);
  });

  it("selection column marks every row of a selected id", async () => {
    const w = mount(DataTable, { props: { columns: cols, rows: grows, groups, selectable: true, selectedIds: [1] } });
    const boxes = w.findAll('input[type="checkbox"]');
    expect(boxes.map((b) => b.element.checked)).toEqual([true, false, true]);
    expect(boxes[1].attributes("aria-label")).toBe("„Zwei“ auswählen");
    await boxes[1].trigger("change");
    expect(w.emitted("toggle-select")[0][0]).toMatchObject({ id: 2 });
  });
});
