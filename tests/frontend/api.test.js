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
});
