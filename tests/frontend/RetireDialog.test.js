import {
  describe,
  it,
  expect,
  vi,
  beforeAll,
  beforeEach,
  afterEach,
} from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ post: vi.fn() }));
import { post } from "../../src/frontend/src/lib/api.js";
import RetireDialog from "../../src/frontend/src/components/RetireDialog.vue";
import { retireReasonLabel } from "../../src/frontend/src/lib/retire.js";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
// Block body: a value returned from beforeEach is called as teardown, and
// mockReset() returns the mock itself.
beforeEach(() => {
  post.mockReset();
});
afterEach(() => (document.body.innerHTML = ""));

const item = { id: 5, display_nr: "TU-0001", label: "Tuba" };
const $ = (sel) => document.querySelector(sel);
const submit = async () => {
  $(".retire-dialog form").dispatchEvent(new Event("submit"));
  await flushPromises();
};

describe("RetireDialog", () => {
  it("needs a reason and posts reason, date and note", async () => {
    post.mockResolvedValue({ ...item, retired_at: "2026-09-30" });
    const w = mount(RetireDialog, {
      props: { open: true, item },
      attachTo: document.body,
    });
    await flushPromises();
    await submit();
    expect(post).not.toHaveBeenCalled();
    expect($(".retire-dialog .form-error").textContent).toBe(
      "Bitte einen Grund wählen",
    );

    const reason = $("#retire-reason");
    reason.value = "sold";
    reason.dispatchEvent(new Event("change"));
    const notes = $("#retire-notes");
    notes.value = "an MV Nachbar";
    notes.dispatchEvent(new Event("input"));
    await submit();
    expect(post).toHaveBeenCalledWith("/items/5/retire", {
      reason: "sold",
      retired_at: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      notes: "an MV Nachbar",
    });
    expect(w.emitted("retired")).toHaveLength(1);
    w.unmount();
  });

  it("shows a refusal inline", async () => {
    post.mockImplementation(async () => {
      throw new Error("Gegenstand ist ausgeliehen – bitte zuerst zurückgeben");
    });
    const w = mount(RetireDialog, {
      props: { open: true, item },
      attachTo: document.body,
    });
    await flushPromises();
    const reason = $("#retire-reason");
    reason.value = "lost";
    reason.dispatchEvent(new Event("change"));
    await submit();
    expect($('.retire-dialog [role="alert"]').textContent).toContain(
      "bitte zuerst zurückgeben",
    );
    w.unmount();
  });

  it("names the reasons", () => {
    expect(retireReasonLabel("returned_to_owner")).toBe(
      "An Eigentümer zurückgegeben",
    );
  });
});
