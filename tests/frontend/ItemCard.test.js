import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import ItemCard from "../../src/frontend/src/components/ItemCard.vue";

const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:p(.*)*", component: { render: () => null } }] });
const item = { id: 7, label: "Tuba", display_nr: "TU-002", manufacturer: "Yamaha", profile_image_url: null, active_loan: null, categories: [] };

function mountCard(props) {
  return mount(ItemCard, { props: { item, hasLoans: true, to: "/instrumente/7", ...props }, global: { plugins: [router] } });
}

describe("ItemCard", () => {
  it("is a link with label, number and status", () => {
    const w = mountCard({});
    const a = w.find("a");
    expect(a.attributes("href")).toBe("/instrumente/7");
    expect(w.text()).toContain("Tuba");
    expect(w.text()).toContain("TU-002 · Yamaha");
    expect(w.find(".badge").text()).toBe("Verfügbar");
    expect(w.find(".item-card-thumb").text()).toBe("TU-002");
  });

  it("becomes a selectable label in selection mode", async () => {
    const w = mountCard({ selecting: true, selected: true });
    expect(w.find("a").exists()).toBe(false);
    const box = w.find('input[type="checkbox"]');
    expect(box.element.checked).toBe(true);
    expect(box.attributes("aria-label")).toBe("„Tuba“ auswählen");
    await box.trigger("change");
    expect(w.emitted("toggle-select")).toHaveLength(1);
  });

  it("shows the profile image", () => {
    const w = mountCard({ item: { ...item, profile_image_url: "/x.jpg" } });
    expect(w.find("img").attributes("src")).toBe("/x.jpg");
    expect(w.find("img").attributes("alt")).toBe("");
  });
});
