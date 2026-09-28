import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../../src/frontend/src/lib/api.js", () => ({
  get: vi.fn(),
  getAll: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

import { get, getAll, post, put, del } from "../../src/frontend/src/lib/api.js";
import ItemDetailPage from "../../src/frontend/src/pages/ItemDetailPage.vue";

const TYPES = [
  { id: 1, label: "Tuba", label_short: "TU" },
  { id: 2, label: "Horn", label_short: "HR" },
];

function baseItem() {
  return {
    id: 1,
    category: "instrument",
    display_nr: "TU-001",
    label: "Tuba",
    quantity: 1,
    instrument_type_id: 1,
    serial_nr: null,
    manufacturer: null,
    construction_year: null,
    distributor: null,
    container: null,
    particularities: null,
    owner: "MV Hofkirchen",
    acquisition_date: null,
    acquisition_cost: null,
    currency_id: null,
    notes: null,
  };
}

// Wrapped in a block body: a reset call returns the mock itself, and Vitest treats
// a value returned from beforeEach as an implicit teardown (see useInlineEdit.test.js /
// pickers.test.js for the same pitfall).
beforeEach(() => {
  get.mockReset();
  getAll.mockReset();
  post.mockReset();
  put.mockReset();
  del.mockReset();

  get.mockImplementation(async (path) => {
    if (path === "/items/1") return baseItem();
    if (path === "/items/1/images") return [];
    if (path === "/items/1/invoices") return [];
    if (path === "/currencies") return [];
    if (path === "/instrument-types") return TYPES;
    throw new Error("unexpected get " + path);
  });
  getAll.mockResolvedValue([]);
  put.mockResolvedValue(baseItem());
});

async function mountPage() {
  const w = mount(ItemDetailPage, {
    props: { category: "instrument", id: 1 },
    attachTo: document.body,
  });
  await flushPromises();
  return w;
}

async function openTypeEditor(w) {
  await w.find('[aria-label="„Typ“ bearbeiten"]').trigger("click");
}

async function chooseTypeAndSave(w, typeId) {
  await w.find(".inline-editor select").setValue(String(typeId));
  await w.find(".inline-editor .inline-save").trigger("click");
}

function renumberDialog(w) {
  return w.findAll(".dialog").find((d) => d.text().includes("Neue Inventarnummer"));
}

describe("ItemDetailPage: Typwechsel mit anderem Kürzel", () => {
  it("asks for confirmation before renumbering; cancel sends nothing and keeps editing", async () => {
    const w = mount(ItemDetailPage, {
      props: { category: "instrument", id: 1 },
      attachTo: document.body,
    });
    await flushPromises();

    await openTypeEditor(w);
    await chooseTypeAndSave(w, 2);

    expect(put).not.toHaveBeenCalled();
    expect(renumberDialog(w)).toBeTruthy();

    const cancelBtn = renumberDialog(w)
      .findAll("button")
      .find((b) => b.text() === "Abbrechen");
    await cancelBtn.trigger("click");

    expect(put).not.toHaveBeenCalled();
    expect(renumberDialog(w)).toBeFalsy();
    expect(w.find(".inline-editor").exists()).toBe(true);

    w.unmount();
  });

  it("commits the type change (and its new label) once confirmed", async () => {
    const w = await mountPage();

    await openTypeEditor(w);
    await chooseTypeAndSave(w, 2);
    expect(put).not.toHaveBeenCalled();

    const confirmBtn = renumberDialog(w)
      .findAll("button")
      .find((b) => b.text() === "Typ ändern");
    await confirmBtn.trigger("click");
    await flushPromises();

    expect(put).toHaveBeenCalledWith("/items/1", { instrument_type_id: 2, label: "Horn" });

    w.unmount();
  });
});
