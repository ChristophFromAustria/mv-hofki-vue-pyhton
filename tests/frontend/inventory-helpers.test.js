import { describe, it, expect } from "vitest";
import { registerLabels } from "../../src/frontend/src/lib/musicians.js";
import {
  splitImages,
  scanTitle,
  isScan,
} from "../../src/frontend/src/lib/images.js";
import {
  sortRegisters,
  reorderUpdates,
  nextSortOrder,
} from "../../src/frontend/src/lib/registers.js";

describe("musician list query", () => {
  it("formats register labels", () => {
    expect(
      registerLabels({ registers: [{ label: "Tuba" }, { label: "Horn" }] }),
    ).toBe("Tuba, Horn");
    expect(registerLabels({ registers: [] })).toBe("—");
    expect(registerLabels({})).toBe("—");
  });
});

describe("item images", () => {
  it("splits photos and scans, treating missing kind as photo", () => {
    const { photos, scans } = splitImages([
      { id: 1, kind: "foto" },
      { id: 2, kind: "scan" },
      { id: 3 },
      { id: 4, kind: "scan" },
    ]);
    expect(photos.map((i) => i.id)).toEqual([1, 3]);
    expect(scans.map((i) => i.id)).toEqual([2, 4]);
    expect(isScan({ kind: "scan" })).toBe(true);
    expect(splitImages(null)).toEqual({ photos: [], scans: [] });
  });

  it("uses the caption as scan title with a fallback", () => {
    expect(scanTitle({ caption: "Datenblatt" }, 0)).toBe("Datenblatt");
    expect(scanTitle({ caption: "  " }, 1)).toBe("Scan 2");
    expect(scanTitle({ caption: null }, 0)).toBe("Scan 1");
  });
});

describe("register ordering", () => {
  const regs = [
    { id: 1, label: "Horn", sort_order: 10 },
    { id: 2, label: "Tuba", sort_order: 20 },
    { id: 3, label: "Posaune", sort_order: 30 },
  ];

  it("sorts by sort_order then label", () => {
    expect(
      sortRegisters([
        { id: 1, label: "B", sort_order: 5 },
        { id: 2, label: "A", sort_order: 5 },
        { id: 3, label: "C", sort_order: 1 },
      ]).map((r) => r.id),
    ).toEqual([3, 2, 1]);
  });

  it("moves a register down and returns only changed positions", () => {
    expect(reorderUpdates(regs, 0, 1)).toEqual([
      { id: 2, sort_order: 10 },
      { id: 1, sort_order: 20 },
    ]);
  });

  it("renumbers irregular orders", () => {
    const irregular = [
      { id: 1, label: "A", sort_order: 1 },
      { id: 2, label: "B", sort_order: 2 },
    ];
    expect(reorderUpdates(irregular, 1, -1)).toEqual([
      { id: 2, sort_order: 10 },
      { id: 1, sort_order: 20 },
    ]);
  });

  it("refuses moves beyond the ends", () => {
    expect(reorderUpdates(regs, 0, -1)).toEqual([]);
    expect(reorderUpdates(regs, 2, 1)).toEqual([]);
  });

  it("computes the next sort order", () => {
    expect(nextSortOrder(regs)).toBe(40);
    expect(nextSortOrder([])).toBe(10);
    expect(nextSortOrder([{ sort_order: 7 }])).toBe(10);
  });
});
