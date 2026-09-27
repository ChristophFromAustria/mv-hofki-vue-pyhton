import { describe, it, expect } from "vitest";
import { toggleId, uniqueIds } from "../../src/frontend/src/lib/bulkSelection.js";

describe("bulk selection", () => {
  it("toggles an id", () => {
    expect(toggleId([1, 2], 3)).toEqual([1, 2, 3]);
    expect(toggleId([1, 2], 1)).toEqual([2]);
  });
  it("collects each item once even when it appears in several groups", () => {
    expect(uniqueIds([{ id: 1 }, { id: 2 }, { id: 1 }])).toEqual([1, 2]);
  });
});
