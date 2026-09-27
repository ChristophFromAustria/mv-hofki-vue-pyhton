import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import GroupHeader from "../../src/frontend/src/components/GroupHeader.vue";

describe("GroupHeader", () => {
  it("shows label and count and toggles", async () => {
    const w = mount(GroupHeader, { props: { label: "Tuba", count: 7, collapsed: false } });
    const btn = w.find("button");
    expect(btn.text()).toContain("Tuba");
    expect(btn.text()).toContain("7");
    expect(btn.attributes("aria-expanded")).toBe("true");
    await btn.trigger("click");
    expect(w.emitted("toggle")).toHaveLength(1);
  });

  it("marks collapsed and omits a missing count", () => {
    const w = mount(GroupHeader, { props: { label: "Horn", count: null, collapsed: true } });
    expect(w.find("button").attributes("aria-expanded")).toBe("false");
    expect(w.find(".group-count").exists()).toBe(false);
  });
});
