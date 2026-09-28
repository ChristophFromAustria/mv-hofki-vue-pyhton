import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import NotesBlock from "../../src/frontend/src/components/NotesBlock.vue";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});

function mountBlock(props) {
  return mount(NotesBlock, {
    props: {
      label: "Notizen",
      value: "hallo **welt**",
      maxLength: 10000,
      saving: false,
      saved: false,
      error: "",
      editing: false,
      ...props,
    },
    attachTo: document.body,
  });
}

describe("NotesBlock", () => {
  it("renders the label, the markdown value and a named edit button", () => {
    const w = mountBlock({});
    expect(w.find("h3").text()).toBe("Notizen");
    expect(w.find(".markdown-text").html()).toContain("<strong>welt</strong>");
    expect(w.find('button[aria-label="„Notizen“ bearbeiten"]').exists()).toBe(true);
  });

  it("emits start when the edit button is clicked", async () => {
    const w = mountBlock({});
    await w.find('button[aria-label="„Notizen“ bearbeiten"]').trigger("click");
    expect(w.emitted("start")).toHaveLength(1);
  });

  it("shows the dialog when editing, and forwards save/cancel", async () => {
    const w = mountBlock({ editing: true });
    expect(w.findComponent({ name: "NotesEditorDialog" }).props("open")).toBe(true);
    await w.findComponent({ name: "NotesEditorDialog" }).vm.$emit("save", "neuer Text");
    expect(w.emitted("save")).toEqual([["neuer Text"]]);
    await w.findComponent({ name: "NotesEditorDialog" }).vm.$emit("cancel");
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("shows a persistent [role=status] for saved state", () => {
    const w = mountBlock({ saved: true });
    expect(w.find('[role="status"]').text()).toBe("Gespeichert");
  });
});
