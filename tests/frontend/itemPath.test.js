import { describe, it, expect } from "vitest";
import { itemPath } from "../../src/frontend/src/lib/categories.js";

describe("itemPath", () => {
  it("puts the inventory number into the item's URL", () => {
    expect(itemPath({ category: "instrument", display_nr: "TR-0006", id: 119 })).toBe(
      "/instrumente/TR-0006",
    );
    expect(itemPath({ category: "general_item", display_nr: "A-0001", id: 5 })).toBe(
      "/allgemein/A-0001",
    );
  });

  it("falls back to the id while the number is unknown", () => {
    expect(itemPath({ category: "clothing", id: 7 })).toBe("/kleidung/7");
  });
});
