import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import ScanDocuments from "../../src/frontend/src/components/ScanDocuments.vue";

beforeAll(() => {
  // jsdom has no native <dialog> behaviour
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

const scans = [
  {
    id: 11,
    url: "/a.jpg",
    kind: "scan",
    caption: "Scan Tuba/p01 – Datenblatt",
  },
  { id: 12, url: "/b.jpg", kind: "scan", caption: null },
];

describe("ScanDocuments", () => {
  it("lists scans with caption and fallback title", () => {
    const w = mount(ScanDocuments, { props: { scans } });
    const captions = w.findAll(".scan-caption").map((c) => c.text());
    expect(captions).toEqual(["Scan Tuba/p01 – Datenblatt", "Scan 2"]);
  });

  it("opens the dialog on a tile and pages through", async () => {
    const w = mount(ScanDocuments, {
      props: { scans },
      attachTo: document.body,
    });
    await w.findAll(".scan-tile")[0].trigger("click");
    await new Promise((r) => setTimeout(r));
    const dialog = w.find("dialog");
    expect(dialog.attributes("open")).toBeDefined();
    expect(w.find("#scan-dialog-title").text()).toBe(
      "Scan Tuba/p01 – Datenblatt",
    );
    await w.find('[aria-label="Nächste Seite"]').trigger("click");
    expect(w.find("#scan-dialog-title").text()).toBe("Scan 2");
    expect(w.text()).toContain("Seite 2 von 2");
    w.unmount();
  });

  it("asks before emitting delete", async () => {
    const w = mount(ScanDocuments, {
      props: { scans, canManage: true },
      attachTo: document.body,
    });
    await w.findAll(".scan-tile")[1].trigger("click");
    await new Promise((r) => setTimeout(r));
    const delBtn = w.findAll("button").find((b) => b.text() === "Löschen");
    await delBtn.trigger("click");
    expect(w.emitted("delete")).toBeUndefined();
    await w
      .findAll("button")
      .find((b) => b.text() === "Ja, löschen")
      .trigger("click");
    expect(w.emitted("delete")[0]).toEqual([12]);
    w.unmount();
  });
});
