import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import FilterBar from "../../src/frontend/src/components/FilterBar.vue";

const defs = [
  {
    key: "is_active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Aktiv" },
      { value: false, label: "Inaktiv" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "register_id__in",
    label: "Register",
    type: "multiselect",
    options: [
      { value: "1", label: "Flöte" },
      { value: "2", label: "Tuba" },
    ],
  },
  { key: "owner", label: "Eigentümer", type: "select", options: [{ value: "MV", label: "MV" }] },
  { keys: ["y__gte", "y__lte"], label: "Baujahr", type: "range" },
  { key: "without_category", label: "Ohne Kategorie", type: "toggle" },
];
const defaults = {
  is_active: true,
  register_id__in: [],
  owner: "",
  y__gte: null,
  y__lte: null,
  without_category: null,
};

function mountBar(state) {
  return mount(FilterBar, { props: { defs, defaults, state: { ...defaults, ...state } } });
}

describe("FilterBar", () => {
  it("shows no chips for defaults", () => {
    const w = mountBar({});
    expect(w.find(".filter-chips").exists()).toBe(false);
    expect(w.find('[aria-pressed="true"]').text()).toBe("Aktiv");
  });

  it("shows chips for non-default values, including 'Alle' against a non-empty default", () => {
    const w = mountBar({ is_active: null, register_id__in: ["2", "1"], y__gte: 1990 });
    const chips = w.findAll(".filter-chips .category-chip").map((c) => c.text());
    expect(chips).toEqual([
      "Status: Alle✕",
      "Register: Tuba, Flöte✕",
      "Baujahr: 1990–…✕",
    ]);
  });

  it("removing a chip emits the defaults of its keys", async () => {
    const w = mountBar({ y__gte: 1990, y__lte: 2000 });
    await w.find('button[aria-label="Filter „Baujahr“ entfernen"]').trigger("click");
    expect(w.emitted("change")).toEqual([
      ["y__gte", null],
      ["y__lte", null],
    ]);
  });

  it("segmented, multiselect, select, toggle and reset emit changes", async () => {
    const w = mountBar({ register_id__in: ["1"] });
    await w.findAll('[role="group"] button')[1].trigger("click");
    const boxes = w.findAll('input[type="checkbox"]');
    await boxes[1].setValue(true);
    await boxes[0].setValue(false);
    await w.find("select").setValue("MV");
    await boxes[2].setValue(true);
    await w.find('button[aria-label="Filter „Register“ entfernen"]').trigger("click");
    expect(w.emitted("change")).toEqual([
      ["is_active", false],
      ["register_id__in", ["1", "2"]],
      ["register_id__in", []],
      ["owner", "MV"],
      ["without_category", true],
      ["register_id__in", []],
    ]);
    await w.find(".filter-reset").trigger("click");
    expect(w.emitted("reset")).toHaveLength(1);
  });

  it("the phone toggle reports the active count", () => {
    const w = mountBar({ owner: "MV" });
    const toggle = w.find(".filter-toggle");
    expect(toggle.text()).toBe("Filter (1)");
    expect(toggle.attributes("aria-expanded")).toBe("false");
  });
});
