import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import MarkdownText from "../../src/frontend/src/components/MarkdownText.vue";

describe("MarkdownText", () => {
  it("renders markdown as HTML inside .markdown-text", () => {
    const w = mount(MarkdownText, { props: { text: "**fett**" } });
    expect(w.find(".markdown-text").html()).toContain("<strong>fett</strong>");
  });

  it("shows a muted em dash for empty/null text", () => {
    const w = mount(MarkdownText, { props: { text: null } });
    expect(w.text()).toBe("—");
    expect(w.find(".markdown-text").classes()).toContain("is-empty");

    const w2 = mount(MarkdownText, { props: { text: "" } });
    expect(w2.text()).toBe("—");
  });
});
