import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import CollapsibleSection from "../../src/frontend/src/components/CollapsibleSection.vue";

beforeEach(() => localStorage.clear());

function mountSection(extra = {}) {
  return mount(CollapsibleSection, {
    props: { scope: "instrument", section: "invoices", title: "Rechnungen", summary: "2 · 150,00 €", ...extra },
    slots: {
      default: "<p class='body'>Inhalt</p>",
      actions: "<button class='act'>Neue Rechnung</button>",
    },
  });
}

describe("CollapsibleSection", () => {
  it("is a heading with a disclosure button controlling the content", () => {
    const w = mountSection();
    const btn = w.find("h2 button");
    expect(btn.text()).toContain("Rechnungen");
    expect(btn.attributes("aria-expanded")).toBe("true");
    const panel = w.find(`#${btn.attributes("aria-controls")}`);
    expect(panel.exists()).toBe(true);
    expect(w.find(".body").isVisible()).toBe(true);
    expect(w.find(".section-summary").exists()).toBe(false);
  });

  it("collapses, shows the summary and keeps actions usable", async () => {
    const w = mountSection();
    await w.find("h2 button").trigger("click");
    expect(w.find("h2 button").attributes("aria-expanded")).toBe("false");
    expect(w.find(".body").exists()).toBe(false);
    expect(w.find(".section-summary").text()).toBe("2 · 150,00 €");
    expect(w.find(".act").exists()).toBe(true);
    expect(localStorage.getItem("detail-collapsed:instrument:invoices")).toBe("1");
  });

  it("restores the saved state", () => {
    localStorage.setItem("detail-collapsed:instrument:invoices", "1");
    const w = mountSection();
    expect(w.find("h2 button").attributes("aria-expanded")).toBe("false");
  });
});
