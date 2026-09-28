import { describe, it, expect } from "vitest";
import { formatDate, formatMoney } from "../../src/frontend/src/lib/format.js";

describe("format", () => {
  it("dates", () => {
    expect(formatDate("2026-03-01")).toBe("01.03.2026");
    expect(formatDate(null)).toBe("—");
    expect(formatDate("")).toBe("—");
  });
  it("money", () => {
    expect(formatMoney(1250, "€")).toBe(`${(1250).toLocaleString("de-AT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`);
    expect(formatMoney(0.5, "CHF")).toBe(`${(0.5).toLocaleString("de-AT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} CHF`);
    expect(formatMoney(null, "€")).toBe("—");
  });
});
