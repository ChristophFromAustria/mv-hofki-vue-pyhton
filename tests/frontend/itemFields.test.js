import { describe, it, expect } from "vitest";
import { itemFieldDefs, renumberPrefix } from "../../src/frontend/src/lib/itemFields.js";

const ctx = {
  types: [
    { id: 1, label: "Tuba", label_short: "TU" },
    { id: 2, label: "Horn", label_short: "HR" },
    { id: 3, label: "Basstuba", label_short: "TU" },
  ],
  genres: [{ id: 7, label: "Marsch" }],
  categories: [{ id: 9, label: "Deko" }],
  currencies: [{ id: 4, abbreviation: "€" }],
};
const keys = (cat) => itemFieldDefs(cat, ctx).map((f) => f.key);

describe("itemFieldDefs", () => {
  it("lists the fields per kind", () => {
    expect(keys("instrument")).toEqual([
      "type", "quantity", "serial_nr", "manufacturer", "construction_year", "distributor",
      "container", "particularities", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("clothing")).toEqual([
      "type", "quantity", "size", "gender", "manufacturer", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("sheet_music")).toEqual([
      "label", "quantity", "composer", "arranger", "difficulty", "genre", "storage_location",
      "manufacturer", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("general_item")).toEqual([
      "label", "quantity", "categories", "storage_location", "manufacturer", "owner",
      "acquisition_date", "acquisition_cost", "notes",
    ]);
  });

  it("type changes also set the label", () => {
    const type = itemFieldDefs("instrument", ctx).find((f) => f.key === "type");
    expect(type.required).toBe(true);
    expect(type.value({ instrument_type_id: 1 })).toBe(1);
    expect(type.toPatch(2)).toEqual({ instrument_type_id: 2, label: "Horn" });
    const clothing = itemFieldDefs("clothing", { ...ctx, types: [{ id: 5, label: "Hut" }] }).find((f) => f.key === "type");
    expect(clothing.toPatch(5)).toEqual({ clothing_type_id: 5, label: "Hut" });
  });

  it("money, categories and genre map to the API fields", () => {
    const defs = Object.fromEntries(itemFieldDefs("general_item", ctx).map((f) => [f.key, f]));
    expect(defs.acquisition_cost.value({ acquisition_cost: 12, currency_id: 4 })).toEqual({ amount: 12, currency_id: 4 });
    expect(defs.acquisition_cost.toPatch({ amount: null, currency_id: null })).toEqual({ acquisition_cost: null, currency_id: null });
    expect(defs.categories.value({ categories: [{ id: 9, label: "Deko" }] })).toEqual([9]);
    expect(defs.categories.toPatch([9])).toEqual({ category_ids: [9] });
    const genre = itemFieldDefs("sheet_music", ctx).find((f) => f.key === "genre");
    expect(genre.toPatch(null)).toEqual({ genre_id: null });
    const year = itemFieldDefs("instrument", ctx).find((f) => f.key === "construction_year");
    expect(year.min).toBe(1800);
    expect(year.max).toBe(new Date().getFullYear() + 1);
  });

  it("marks long text fields as block fields with a character limit", () => {
    const notes = itemFieldDefs("general_item", ctx).find((f) => f.key === "notes");
    expect(notes.block).toBe(true);
    expect(notes.maxLength).toBe(10000);
    const particularities = itemFieldDefs("instrument", ctx).find(
      (f) => f.key === "particularities",
    );
    expect(particularities.block).toBe(true);
    expect(particularities.maxLength).toBe(500);
  });

  it("detects renumbering only when the short code changes", () => {
    const item = { category: "instrument", number_prefix: "TU" };
    expect(renumberPrefix(item, 2, ctx.types)).toBe("HR");
    expect(renumberPrefix(item, 3, ctx.types)).toBe(null);
    expect(renumberPrefix({ category: "clothing", number_prefix: "K" }, 2, ctx.types)).toBe(null);
    // number_prefix may be absent from the API response; fall back to display_nr's prefix.
    expect(renumberPrefix({ category: "instrument", display_nr: "TU-002" }, 2, ctx.types)).toBe("HR");
  });
});
