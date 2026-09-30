import { describe, it, expect } from "vitest";
import { isOverdue, loanStatus, todayIso } from "../../src/frontend/src/lib/loans.js";

const TODAY = "2026-09-30";

describe("loans", () => {
  it("todayIso uses the local date", () => {
    expect(todayIso(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });

  it("is overdue only while open and after the planned day", () => {
    expect(isOverdue({ end_date: null, due_date: "2026-09-29" }, TODAY)).toBe(true);
    expect(isOverdue({ end_date: null, due_date: "2026-09-30" }, TODAY)).toBe(false);
    expect(isOverdue({ end_date: null, due_date: null }, TODAY)).toBe(false);
    expect(isOverdue({ end_date: "2026-09-30", due_date: "2026-01-01" }, TODAY)).toBe(false);
    expect(isOverdue(null, TODAY)).toBe(false);
  });

  it("names the status with its badge", () => {
    expect(loanStatus({ end_date: "2026-01-01" }, TODAY)).toEqual({
      label: "Zurückgegeben",
      badge: "badge badge-gray",
    });
    expect(loanStatus({ end_date: null, due_date: "2026-01-01" }, TODAY).label).toBe("Überfällig");
    expect(loanStatus({ end_date: null, due_date: "2999-01-01" }, TODAY).label).toBe("Ausgeliehen");
  });
});
