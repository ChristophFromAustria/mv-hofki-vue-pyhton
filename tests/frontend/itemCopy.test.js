import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ post: vi.fn() }));
import { post } from "../../src/frontend/src/lib/api.js";
import {
  copyChoices,
  copyPayload,
  defaultCopyKeys,
} from "../../src/frontend/src/lib/itemCopy.js";
import CopyItemDialog from "../../src/frontend/src/components/CopyItemDialog.vue";

const tuba = {
  id: 7,
  display_nr: "TU-0003",
  label: "Tuba B",
  instrument_type_id: 2,
  manufacturer: "Melton",
  owner: "MV Hofkirchen",
  serial_nr: "S-123",
  notes: "Delle am Schallstück",
  acquisition_date: "2020-05-01",
  acquisition_cost: 4000,
  currency_id: 1,
  quantity: 1,
  construction_year: null,
  storage_location: "",
};

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
// Block body: a value returned from beforeEach is called as teardown.
beforeEach(() => {
  post.mockReset();
});
afterEach(() => (document.body.innerHTML = ""));

describe("itemCopy", () => {
  it("offers only fields with a value, the type always", () => {
    const keys = copyChoices(tuba, "instrument").map((c) => c.key);
    expect(keys).toEqual([
      "type",
      "quantity",
      "manufacturer",
      "owner",
      "acquisition",
      "serial_nr",
      "notes",
    ]);
    expect(copyChoices({ id: 1, label: "x" }, "instrument").map((c) => c.key)).toEqual(["type"]);
  });

  it("leaves per-piece values off by default", () => {
    expect(defaultCopyKeys(copyChoices(tuba, "instrument"))).toEqual([
      "type",
      "quantity",
      "manufacturer",
      "owner",
      "acquisition",
    ]);
  });

  it("builds the new item from the chosen values; the type always comes along", () => {
    expect(copyPayload(tuba, "instrument", ["manufacturer", "acquisition"], "Tuba C")).toEqual({
      category: "instrument",
      label: "Tuba C",
      instrument_type_id: 2,
      manufacturer: "Melton",
      acquisition_date: "2020-05-01",
      acquisition_cost: 4000,
      currency_id: 1,
    });
    const hat = { id: 3, label: "Hut", categories: [{ id: 4, label: "Tracht" }] };
    expect(copyPayload(hat, "general_item", ["categories"], "Hut")).toEqual({
      category: "general_item",
      label: "Hut",
      category_ids: [4],
    });
  });
});

describe("CopyItemDialog", () => {
  it("creates the chosen number of copies and reports them", async () => {
    post.mockImplementation(async (_path, body) => ({ ...body, id: 100, display_nr: "TU-0004" }));
    const w = mount(CopyItemDialog, {
      props: { open: true, item: tuba, category: "instrument" },
      attachTo: document.body,
    });
    await flushPromises();
    const input = (id) => document.getElementById(id);
    expect(input("copy-label").value).toBe("Tuba B");
    input("copy-count").value = "3";
    input("copy-count").dispatchEvent(new Event("input"));
    document.querySelector(".copy-dialog form").dispatchEvent(new Event("submit"));
    await flushPromises();
    expect(post).toHaveBeenCalledTimes(3);
    expect(post.mock.calls[0][1]).not.toHaveProperty("serial_nr");
    expect(post.mock.calls[0][1]).not.toHaveProperty("notes");
    expect(w.emitted("copied")[0][0]).toHaveLength(3);
    w.unmount();
  });

  it("stays open with a clear message when a copy fails halfway", async () => {
    let n = 0;
    post.mockImplementation(async (_path, body) => {
      if (++n === 2) throw new Error("Serverfehler");
      return { ...body, id: 100 + n };
    });
    const w = mount(CopyItemDialog, {
      props: { open: true, item: tuba, category: "instrument" },
      attachTo: document.body,
    });
    await flushPromises();
    const count = document.getElementById("copy-count");
    count.value = "3";
    count.dispatchEvent(new Event("input"));
    document.querySelector(".copy-dialog form").dispatchEvent(new Event("submit"));
    await flushPromises();
    expect(document.querySelector('.copy-dialog [role="alert"]').textContent).toBe(
      "1 von 3 angelegt, dann fehlgeschlagen: Serverfehler",
    );
    expect(w.emitted("copied")).toBeUndefined();
    w.unmount();
  });
});
