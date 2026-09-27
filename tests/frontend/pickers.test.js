import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
import { get } from "../../src/frontend/src/lib/api.js";
import {
  fetchMusicianOptions,
  fetchLoanableItemOptions,
} from "../../src/frontend/src/lib/pickers.js";

// Wrapped in a block body: `get.mockReset()` returns the mock function itself, and
// Vitest calls a value returned from beforeEach as an implicit teardown afterwards,
// which would invoke get() a spurious extra time with no arguments.
beforeEach(() => {
  get.mockReset();
});

describe("pickers", () => {
  it("musician options: active only, max 20, search optional", async () => {
    get.mockResolvedValue({
      items: [{ id: 3, first_name: "Anna", last_name: "Maier", is_extern: true }],
      total: 1,
    });
    const opts = await fetchMusicianOptions("mai");
    expect(get).toHaveBeenCalledWith("/musicians?is_active=true&limit=20&search=mai");
    expect(opts).toEqual([{ id: 3, label: "Maier Anna", description: "extern" }]);
    await fetchMusicianOptions("", { activeOnly: false });
    expect(get).toHaveBeenLastCalledWith("/musicians?limit=20");
  });

  it("loanable items: three categories, available only, labelled", async () => {
    get.mockImplementation(async (path) => ({
      items: path.includes("instrument")
        ? [{ id: 1, display_nr: "TU-002", label: "Tuba", category: "instrument" }]
        : [],
      total: 0,
    }));
    const opts = await fetchLoanableItemOptions("tu");
    expect(get.mock.calls.map((c) => c[0])).toEqual([
      "/items?category=instrument&status=verfuegbar&limit=7&search=tu",
      "/items?category=clothing&status=verfuegbar&limit=7&search=tu",
      "/items?category=general_item&status=verfuegbar&limit=7&search=tu",
    ]);
    expect(opts).toEqual([{ id: 1, label: "TU-002 Tuba", description: "Instrument" }]);
  });
});
