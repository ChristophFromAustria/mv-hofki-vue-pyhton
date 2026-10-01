import { describe, it, expect, beforeEach } from "vitest";
import {
  datasheetUrl,
  loadSections,
  saveSections,
} from "../../src/frontend/src/lib/printing.js";

beforeEach(() => {
  localStorage.clear();
});

describe("printing", () => {
  it("builds the URL for one item", () => {
    expect(datasheetUrl({ category: "instrument", itemId: 119, sections: ["photo", "notes"] })).toBe(
      "/api/v1/print/datasheets?category=instrument&item_id=119&sections=photo%2Cnotes",
    );
  });

  it("takes the list's filters but not its paging or grouping", () => {
    const listParams = new URLSearchParams(
      "category=instrument&search=tuba&status=verliehen&group_by=type&order_by=-number&limit=50&offset=50",
    );
    const url = new URL(datasheetUrl({ category: "instrument", listParams, sections: [] }), "http://x");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      category: "instrument",
      search: "tuba",
      status: "verliehen",
      order_by: "-number",
      sections: "",
    });
  });

  it("remembers the chosen sections in the browser", () => {
    expect(loadSections()).toEqual(["photo", "loan", "loan_history"]);
    saveSections(["notes", "unknown"]);
    expect(loadSections()).toEqual(["notes"]);
  });
});
