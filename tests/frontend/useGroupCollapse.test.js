import { describe, it, expect, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { useGroupCollapse } from "../../src/frontend/src/composables/useGroupCollapse.js";

beforeEach(() => {
  localStorage.clear();
});

const GROUPS = [
  { key: "3", label: "Trompete", count: 4 },
  { key: "5", label: "Horn", count: 2 },
];

describe("useGroupCollapse", () => {
  it("starts with every group collapsed", () => {
    const { collapsed, allExpanded } = useGroupCollapse(ref("instrument:type"), ref(GROUPS));
    expect([...collapsed.value].sort()).toEqual(["3", "5"]);
    expect(allExpanded.value).toBe(false);
  });

  it("toggles and persists per storage key", async () => {
    const key = ref("instrument:type");
    const { collapsed, toggle } = useGroupCollapse(key, ref(GROUPS));
    toggle("5");
    expect([...collapsed.value].sort()).toEqual(["3"]);
    expect(JSON.parse(localStorage.getItem("groups-expanded:instrument:type"))).toEqual(["5"]);
    key.value = "instrument:status";
    await nextTick();
    // new key has no persisted expanded set -> all collapsed again
    expect([...collapsed.value].sort()).toEqual(["3", "5"]);
    key.value = "instrument:type";
    await nextTick();
    expect([...collapsed.value].sort()).toEqual(["3"]);
    toggle("5");
    expect([...collapsed.value].sort()).toEqual(["3", "5"]);
  });

  it("expandAll expands every current group and persists", () => {
    const key = ref("instrument:type");
    const { collapsed, expandAll, allExpanded } = useGroupCollapse(key, ref(GROUPS));
    expandAll();
    expect([...collapsed.value]).toEqual([]);
    expect(allExpanded.value).toBe(true);
    expect(JSON.parse(localStorage.getItem("groups-expanded:instrument:type")).sort()).toEqual([
      "3",
      "5",
    ]);
  });

  it("collapseAll clears the expanded set and persists", () => {
    const key = ref("instrument:type");
    const groups = ref(GROUPS);
    const { collapsed, expandAll, collapseAll, allExpanded } = useGroupCollapse(key, groups);
    expandAll();
    collapseAll();
    expect([...collapsed.value].sort()).toEqual(["3", "5"]);
    expect(allExpanded.value).toBe(false);
    expect(JSON.parse(localStorage.getItem("groups-expanded:instrument:type"))).toEqual([]);
  });

  it("allExpanded is false when there are no groups", () => {
    const { allExpanded } = useGroupCollapse(ref("instrument:type"), ref(null));
    expect(allExpanded.value).toBe(false);
  });

  it("collapsed is empty when groups is null", () => {
    const { collapsed, toggle, expandAll } = useGroupCollapse(ref("instrument:type"), ref(null));
    expect([...collapsed.value]).toEqual([]);
    toggle("5");
    expandAll();
    expect([...collapsed.value]).toEqual([]);
  });

  it("ignores old groups-collapsed: entries (no migration)", () => {
    localStorage.setItem("groups-collapsed:instrument:type", JSON.stringify(["3"]));
    const { collapsed } = useGroupCollapse(ref("instrument:type"), ref(GROUPS));
    expect([...collapsed.value].sort()).toEqual(["3", "5"]);
  });

  it("survives broken storage", () => {
    localStorage.setItem("groups-expanded:x", "{kaputt");
    const { collapsed } = useGroupCollapse(ref("x"), ref(GROUPS.map((g) => ({ ...g, key: "3" }))));
    expect([...collapsed.value]).toEqual(["3"]);
  });
});
