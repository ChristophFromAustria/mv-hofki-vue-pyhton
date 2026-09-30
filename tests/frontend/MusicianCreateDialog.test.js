import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ post: vi.fn() }));
import { post } from "../../src/frontend/src/lib/api.js";
import MusicianCreateDialog from "../../src/frontend/src/components/MusicianCreateDialog.vue";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
beforeEach(() => {
  post.mockReset();
});
afterEach(() => (document.body.innerHTML = ""));

function mountDialog(props = {}) {
  return mount(MusicianCreateDialog, {
    props: { open: true, initialText: "Anna Maier", ...props },
    attachTo: document.body,
  });
}
const input = (id) => document.getElementById(id);

describe("MusicianCreateDialog", () => {
  it("prefills the name from the typed text and can swap it", async () => {
    const w = mountDialog();
    await flushPromises();
    expect(input("mc-first").value).toBe("Anna");
    expect(input("mc-last").value).toBe("Maier");
    document.querySelector(".musician-create-swap").click();
    await flushPromises();
    expect(input("mc-first").value).toBe("Maier");
    expect(input("mc-last").value).toBe("Anna");
    w.unmount();
  });

  it("creates the musician and emits it", async () => {
    post.mockResolvedValue({ id: 9, first_name: "Anna", last_name: "Maier" });
    const w = mountDialog();
    await flushPromises();
    document.querySelector(".musician-create-dialog form").dispatchEvent(new Event("submit"));
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/musicians", {
      first_name: "Anna",
      last_name: "Maier",
      is_extern: false,
    });
    expect(w.emitted("created")).toEqual([[{ id: 9, first_name: "Anna", last_name: "Maier" }]]);
    w.unmount();
  });

  it("requires both names and shows errors inline", async () => {
    const w = mountDialog({ initialText: "Maier" });
    await flushPromises();
    document.querySelector(".musician-create-dialog form").dispatchEvent(new Event("submit"));
    await flushPromises();
    expect(post).not.toHaveBeenCalled();
    expect(document.querySelector(".musician-create-dialog .form-error").textContent).toBe("Pflichtfeld");
    post.mockRejectedValue(new Error("Serverfehler"));
    input("mc-first").value = "Anna";
    input("mc-first").dispatchEvent(new Event("input"));
    document.querySelector(".musician-create-dialog form").dispatchEvent(new Event("submit"));
    await flushPromises();
    expect(document.querySelector('.musician-create-dialog [role="alert"]').textContent).toContain(
      "Anlegen fehlgeschlagen: Serverfehler",
    );
    w.unmount();
  });
});
