import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { post } from "../../src/frontend/src/lib/api.js";

function stubFetch(detail) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      text: async () => JSON.stringify({ detail }),
      headers: new Headers(),
    }),
  );
}

describe("api error message handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("joins array detail entries by their msg", async () => {
    stubFetch([{ msg: "String should have at most 50 characters" }, { msg: "zweiter" }]);
    await expect(post("/x", {})).rejects.toThrow(
      "String should have at most 50 characters; zweiter",
    );
  });

  it("keeps a string detail unchanged", async () => {
    stubFetch("Kategorie existiert bereits");
    await expect(post("/x", {})).rejects.toThrow("Kategorie existiert bereits");
  });

  it("strips a leading pydantic 'Value error, ' from a msg", async () => {
    stubFetch([{ msg: "Value error, „x“ ist kein gültiger Sortierschlüssel." }]);
    try {
      await post("/x", {});
      throw new Error("expected post() to reject");
    } catch (e) {
      expect(e.message).toBe("„x“ ist kein gültiger Sortierschlüssel.");
    }
  });
});

describe("getAll", () => {
  it("pages until total and appends limit/offset to paths with a query", async () => {
    const pages = [
      { items: [{ id: 1 }, { id: 2 }], total: 3 },
      { items: [{ id: 3 }], total: 3 },
    ];
    const calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        calls.push(url);
        const body = pages[calls.length - 1];
        return {
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => body,
          text: async () => JSON.stringify(body),
        };
      }),
    );
    const { getAll } = await import("../../src/frontend/src/lib/api.js");
    const all = await getAll("/loans?item_id=5", 2);
    expect(all.map((x) => x.id)).toEqual([1, 2, 3]);
    expect(calls[0]).toMatch(/\/api\/v1\/loans\?item_id=5&limit=2&offset=0$/);
    expect(calls[1]).toMatch(/offset=2$/);
  });
});
