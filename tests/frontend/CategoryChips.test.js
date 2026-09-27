import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import CategoryChips from "../../src/frontend/src/components/CategoryChips.vue";

describe("CategoryChips", () => {
  it("renders one chip per category", () => {
    const w = mount(CategoryChips, {
      props: { categories: [{ id: 1, label: "Deko" }, { id: 2, label: "Gastro" }] },
    });
    expect(w.findAll(".category-chip").map((c) => c.text())).toEqual(["Deko", "Gastro"]);
  });

  it("shows a dash without categories", () => {
    const w = mount(CategoryChips, { props: { categories: [] } });
    expect(w.find(".category-chips").exists()).toBe(false);
    expect(w.text()).toBe("—");
  });
});
