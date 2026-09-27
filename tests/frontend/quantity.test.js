import { describe, it, expect } from "vitest";
import {
  itemQuantity,
  quantityCell,
  quantityLabel,
  quantityDetail,
  hasMultipleQuantities,
  validateQuantity,
} from "../../src/frontend/src/lib/quantity.js";

describe("item quantity", () => {
  it("treats missing or invalid quantities as 1", () => {
    expect(itemQuantity({})).toBe(1);
    expect(itemQuantity(null)).toBe(1);
    expect(itemQuantity({ quantity: null })).toBe(1);
    expect(itemQuantity({ quantity: 0 })).toBe(1);
    expect(itemQuantity({ quantity: 2.5 })).toBe(1);
    expect(itemQuantity({ quantity: 4 })).toBe(4);
  });

  it("leaves the table cell empty for a single piece", () => {
    expect(quantityCell({ quantity: 1 })).toBe("");
    expect(quantityCell({})).toBe("");
    expect(quantityCell({ quantity: 12 })).toBe("12");
  });

  it("labels cards only when there is more than one piece", () => {
    expect(quantityLabel({ quantity: 1 })).toBe("");
    expect(quantityLabel({ quantity: 3 })).toBe("3 Stück");
  });

  it("always shows a value on the detail page", () => {
    expect(quantityDetail({})).toBe("1 Stück");
    expect(quantityDetail({ quantity: 7 })).toBe("7 Stück");
  });

  it("detects whether a list needs the quantity column", () => {
    expect(hasMultipleQuantities([{ quantity: 1 }, {}])).toBe(false);
    expect(hasMultipleQuantities([{ quantity: 1 }, { quantity: 2 }])).toBe(
      true,
    );
    expect(hasMultipleQuantities(null)).toBe(false);
  });

  it("validates form input", () => {
    expect(validateQuantity(1)).toBe("");
    expect(validateQuantity(25)).toBe("");
    expect(validateQuantity("")).toBe("Pflichtfeld");
    expect(validateQuantity(null)).toBe("Pflichtfeld");
    expect(validateQuantity(0)).toBe("Mindestens 1");
    expect(validateQuantity(-3)).toBe("Mindestens 1");
    expect(validateQuantity(1.5)).toBe("Nur ganze Zahlen");
  });
});
