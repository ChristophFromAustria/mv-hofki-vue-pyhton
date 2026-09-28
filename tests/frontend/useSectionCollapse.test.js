import { describe, it, expect, beforeEach } from "vitest";
import { useSectionCollapse } from "../../src/frontend/src/composables/useSectionCollapse.js";

beforeEach(() => localStorage.clear());

describe("useSectionCollapse", () => {
  it("defaults to open, toggles and persists per scope and section", () => {
    const a = useSectionCollapse("instrument", "master");
    expect(a.open.value).toBe(true);
    a.toggle();
    expect(a.open.value).toBe(false);
    expect(localStorage.getItem("detail-collapsed:instrument:master")).toBe("1");
    expect(useSectionCollapse("instrument", "master").open.value).toBe(false);
    expect(useSectionCollapse("clothing", "master").open.value).toBe(true);
    a.toggle();
    expect(localStorage.getItem("detail-collapsed:instrument:master")).toBe(null);
  });

  it("works when storage throws", () => {
    const orig = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    try {
      const s = useSectionCollapse("x", "y");
      expect(s.open.value).toBe(true);
      s.toggle();
      expect(s.open.value).toBe(false);
    } finally {
      Storage.prototype.getItem = orig;
    }
  });
});
