import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import GroupToggleAll from "../../src/frontend/src/components/GroupToggleAll.vue";

describe("GroupToggleAll", () => {
  it("offers to expand all when collapsed and emits expand-all", async () => {
    const w = mount(GroupToggleAll, { props: { allExpanded: false } });
    const btn = w.find("button");
    expect(btn.attributes("aria-label")).toBe("Alle Gruppen aufklappen");
    expect(btn.attributes("title")).toBe("Alle Gruppen aufklappen");
    await btn.trigger("click");
    expect(w.emitted("expand-all")).toHaveLength(1);
    expect(w.emitted("collapse-all")).toBeUndefined();
  });

  it("offers to collapse all when expanded and emits collapse-all", async () => {
    const w = mount(GroupToggleAll, { props: { allExpanded: true } });
    const btn = w.find("button");
    expect(btn.attributes("aria-label")).toBe("Alle Gruppen zuklappen");
    expect(btn.attributes("title")).toBe("Alle Gruppen zuklappen");
    await btn.trigger("click");
    expect(w.emitted("collapse-all")).toHaveLength(1);
    expect(w.emitted("expand-all")).toBeUndefined();
  });

  it("hides the icon from assistive tech and supports disabled", () => {
    const w = mount(GroupToggleAll, { props: { allExpanded: false, disabled: true } });
    expect(w.find("button").attributes("disabled")).toBeDefined();
    expect(w.find("[aria-hidden]").exists()).toBe(true);
  });
});
