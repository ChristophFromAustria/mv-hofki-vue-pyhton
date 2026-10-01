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

describe("labels", async () => {
  const { labelUrl, loadLabelSettings, saveLabelSettings, DEFAULT_LABEL_SETTINGS } = await import(
    "../../src/frontend/src/lib/printing.js"
  );

  it("builds the URL of a preset and of custom sizes", () => {
    const preset = { ...DEFAULT_LABEL_SETTINGS, template: "a4-70x37", start: 5, logo: false };
    expect(labelUrl({ category: "instrument", itemId: 119, settings: preset })).toBe(
      "/api/v1/print/labels?category=instrument&item_id=119&template=a4-70x37&logo=false&frame=false&start=5",
    );
    const custom = {
      ...DEFAULT_LABEL_SETTINGS,
      template: "custom",
      frame: true,
      custom: { ...DEFAULT_LABEL_SETTINGS.custom, width: 50, height: 30, cols: 4, rows: 9 },
    };
    const url = new URL(labelUrl({ category: "clothing", settings: custom }), "http://x");
    expect(url.searchParams.get("template")).toBe("custom");
    expect(url.searchParams.get("width")).toBe("50");
    expect(url.searchParams.get("cols")).toBe("4");
    expect(url.searchParams.get("frame")).toBe("true");
    expect(url.searchParams.has("start")).toBe(false);
  });

  it("remembers format and options, but always starts a sheet at 1", () => {
    expect(loadLabelSettings().template).toBe("roll-62x29");
    saveLabelSettings({ ...DEFAULT_LABEL_SETTINGS, template: "a4-63x38", start: 7, logo: false });
    const loaded = loadLabelSettings();
    expect(loaded).toMatchObject({ template: "a4-63x38", logo: false, start: 1 });
    expect(loaded.custom.width).toBe(62);
  });
});
