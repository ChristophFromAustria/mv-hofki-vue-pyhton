import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SortSelect from "../../src/frontend/src/components/SortSelect.vue";

const options = [
  { key: "number", label: "Nummer" },
  { key: "type", label: "Typ" },
];

describe("SortSelect", () => {
  it("changes the key keeping the direction and flips the direction", async () => {
    const w = mount(SortSelect, { props: { options, modelValue: "-number" } });
    await w.find("select").setValue("type");
    await w.find("button").trigger("click");
    expect(w.emitted("update:modelValue")).toEqual([["-type"], ["number"]]);
    expect(w.find("button").attributes("aria-label")).toBe(
      "Absteigend sortiert – auf aufsteigend umschalten",
    );
  });
});
