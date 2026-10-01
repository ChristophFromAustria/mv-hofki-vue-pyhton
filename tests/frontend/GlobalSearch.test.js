import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
import { get } from "../../src/frontend/src/lib/api.js";
import GlobalSearch from "../../src/frontend/src/components/GlobalSearch.vue";

const item = (id, nr, label) => ({ id, category: "instrument", display_nr: nr, label, manufacturer: null, notes: null, active_loan: null });

function response(query, { exact = null } = {}) {
  return {
    query,
    exact,
    items: [{ category: "instrument", label: "Instrumente", total: 2, hits: [item(1, "TR-0006", "Trompete"), item(2, "TR-0007", "Trompete B")] }],
    musicians: { total: 0, hits: [] },
    invoices: { total: 0, hits: [] },
  };
}

beforeEach(() => {
  push.mockReset();
  get.mockReset();
});
afterEach(() => (document.body.innerHTML = ""));

async function typeInto(w, text) {
  await w.find("input").setValue(text);
  await new Promise((r) => setTimeout(r, 0));
  await flushPromises();
}

function mountSearch() {
  return mount(GlobalSearch, { props: { debounceMs: 0 }, attachTo: document.body });
}

describe("GlobalSearch", () => {
  it("shows grouped hits and asks for at most 3 per area", async () => {
    get.mockResolvedValue(response("trompete"));
    const w = mountSearch();
    await typeInto(w, "trompete");
    expect(get).toHaveBeenCalledWith("/search?q=trompete&limit=3");
    expect(w.findAll('[role="option"]').map((o) => o.text())).toEqual([
      expect.stringContaining("TR-0006"),
      expect.stringContaining("TR-0007"),
      "Alle 2 Treffer anzeigen →",
    ]);
    expect(w.find("input").attributes("aria-expanded")).toBe("true");
  });

  it("Enter on an exact inventory number opens the item, otherwise the search page", async () => {
    get.mockResolvedValue(response("tr 6", { exact: item(1, "TR-0006", "Trompete") }));
    const w = mountSearch();
    await typeInto(w, "tr 6");
    await w.find("input").trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(push).toHaveBeenCalledWith("/instrumente/TR-0006");

    get.mockResolvedValue(response("trompete"));
    await typeInto(w, "trompete");
    await w.find("input").trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(push).toHaveBeenLastCalledWith({ path: "/suche", query: { q: "trompete" } });
  });

  it("arrow keys choose an entry, Enter opens it, Escape closes", async () => {
    get.mockResolvedValue(response("trompete"));
    const w = mountSearch();
    await typeInto(w, "trompete");
    const input = w.find("input");
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    expect(input.attributes("aria-activedescendant")).toMatch(/-opt-1$/);
    await input.trigger("keydown", { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/instrumente/TR-0007");

    await typeInto(w, "trompete");
    await input.trigger("keydown", { key: "Escape" });
    expect(input.attributes("aria-expanded")).toBe("false");
  });

  it("Ctrl+K and / focus the field, but / not while typing elsewhere", async () => {
    const w = mountSearch();
    const other = document.createElement("input");
    document.body.appendChild(other);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();
    expect(document.activeElement).toBe(w.find("input").element);

    other.focus();
    other.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
    await flushPromises();
    expect(document.activeElement).toBe(other);

    document.body.focus();
    other.blur();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "/" }));
    await flushPromises();
    expect(document.activeElement).toBe(w.find("input").element);
  });

  it("says when nothing was found", async () => {
    get.mockResolvedValue({ query: "xyz", exact: null, items: [], musicians: { total: 0, hits: [] }, invoices: { total: 0, hits: [] } });
    const w = mountSearch();
    await typeInto(w, "xyz");
    expect(w.text()).toContain("Keine Treffer für „xyz“.");
  });
});
