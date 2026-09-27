import { describe, it, expect, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { useGroupCollapse } from "../../src/frontend/src/composables/useGroupCollapse.js";

beforeEach(() => localStorage.clear());

describe("useGroupCollapse", () => {
  it("toggles and persists per storage key", async () => {
    const key = ref("instrument:type");
    const { collapsed, toggle } = useGroupCollapse(key);
    toggle("5");
    expect([...collapsed.value]).toEqual(["5"]);
    expect(JSON.parse(localStorage.getItem("groups-collapsed:instrument:type"))).toEqual(["5"]);
    key.value = "instrument:status";
    await nextTick();
    expect([...collapsed.value]).toEqual([]);
    key.value = "instrument:type";
    await nextTick();
    expect([...collapsed.value]).toEqual(["5"]);
    toggle("5");
    expect([...collapsed.value]).toEqual([]);
  });

  it("survives broken storage", () => {
    localStorage.setItem("groups-collapsed:x", "{kaputt");
    const { collapsed } = useGroupCollapse(ref("x"));
    expect([...collapsed.value]).toEqual([]);
  });
});
