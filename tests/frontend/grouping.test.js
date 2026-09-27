import { describe, it, expect } from "vitest";
import { buildSegments } from "../../src/frontend/src/lib/grouping.js";

const rows = [
  { id: 1, _key: "a:1", group_key: "a" },
  { id: 2, _key: "a:2", group_key: "a" },
  { id: 3, _key: "b:3", group_key: "b" },
  { id: 1, _key: "b:1", group_key: "b" },
];
const groups = [
  { key: "a", label: "Alpha", count: 5 },
  { key: "b", label: "Beta", count: 2 },
];

describe("buildSegments", () => {
  it("returns only rows without groups", () => {
    const segs = buildSegments(rows.slice(0, 2), null, new Set());
    expect(segs.map((s) => s.type)).toEqual(["row", "row"]);
    expect(segs[0].key).toBe("a:1");
  });

  it("inserts one header per group run with counts from groups", () => {
    const segs = buildSegments(rows, groups, new Set());
    expect(segs.map((s) => (s.type === "group" ? `G:${s.label}:${s.count}` : s.row._key))).toEqual([
      "G:Alpha:5", "a:1", "a:2", "G:Beta:2", "b:3", "b:1",
    ]);
  });

  it("hides rows of collapsed groups but keeps the header", () => {
    const segs = buildSegments(rows, groups, new Set(["a"]));
    expect(segs.map((s) => (s.type === "group" ? `G:${s.groupKey}:${s.collapsed}` : s.row._key))).toEqual([
      "G:a:true", "G:b:false", "b:3", "b:1",
    ]);
  });

  it("falls back to the row label when a group is not in groups", () => {
    const segs = buildSegments([{ id: 9, _key: "x:9", group_key: "x", group_label: "Xeno" }], groups, new Set());
    expect(segs[0]).toMatchObject({ type: "group", label: "Xeno", count: null });
  });
});
