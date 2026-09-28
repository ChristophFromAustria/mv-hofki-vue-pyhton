import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import NotesEditorDialog from "../../src/frontend/src/components/NotesEditorDialog.vue";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});

function mountDialog(props) {
  return mount(NotesEditorDialog, {
    props: {
      open: true,
      title: "Notizen bearbeiten",
      value: "hallo welt",
      maxLength: 10000,
      saving: false,
      error: "",
      ...props,
    },
    attachTo: document.body,
  });
}

describe("NotesEditorDialog", () => {
  it("resets the draft to value every time it opens", async () => {
    const w = mountDialog({ open: false });
    await w.setProps({ open: true, value: "erster Text" });
    await nextTick();
    expect(w.find("textarea").element.value).toBe("erster Text");

    await w.find("textarea").setValue("geändert, aber nicht gespeichert");
    await w.setProps({ open: false });
    await w.setProps({ open: true, value: "zweiter Text" });
    await nextTick();
    expect(w.find("textarea").element.value).toBe("zweiter Text");
  });

  it("wraps the current selection with the toolbar's Fett button", async () => {
    const w = mountDialog({ value: "hallo welt" });
    await nextTick();
    const ta = w.find("textarea").element;
    ta.focus();
    ta.setSelectionRange(0, 5);
    await w.find('button[aria-label="Fett"]').trigger("click");
    expect(w.find("textarea").element.value).toBe("**hallo** welt");
  });

  it("toggles between Bearbeiten and Vorschau", async () => {
    const w = mountDialog({ value: "**fett**" });
    expect(w.find("textarea").exists()).toBe(true);
    await w.find('button[aria-label="Vorschau"]').trigger("click");
    expect(w.find("textarea").exists()).toBe(false);
    expect(w.find(".markdown-text").html()).toContain("<strong>fett</strong>");
    await w.find('button[aria-label="Bearbeiten"]').trigger("click");
    expect(w.find("textarea").exists()).toBe(true);
  });

  it("counter warns near the limit and disables save over it", async () => {
    const w = mountDialog({ value: "1234567", maxLength: 10 });
    await nextTick();
    expect(w.find("[aria-live='polite']").text()).toContain("7");
    expect(w.find("[aria-live='polite']").text()).toContain("10");
    await w.find("textarea").setValue("12345678901");
    await nextTick();
    expect(w.find('[role="alert"]').text()).toContain("Höchstens 10 Zeichen");
    expect(w.find(".notes-save").attributes("disabled")).toBeDefined();
  });

  it("saves on Ctrl+Enter", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find("textarea").trigger("keydown", { key: "Enter", ctrlKey: true });
    expect(w.emitted("save")).toEqual([["abc def"]]);
  });

  it("asks to discard unsaved changes on Abbrechen, and can resume editing", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find(".notes-cancel").trigger("click");
    expect(w.text()).toContain("Änderungen verwerfen?");
    expect(w.emitted("cancel")).toBeUndefined();

    await w.find('button:not(.notes-cancel)').exists();
    const weiter = w.findAll("button").find((b) => b.text() === "Weiter bearbeiten");
    await weiter.trigger("click");
    expect(w.find("textarea").element.value).toBe("abc def");

    await w.find(".notes-cancel").trigger("click");
    const verwerfen = w.findAll("button").find((b) => b.text() === "Verwerfen");
    await verwerfen.trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("cancels immediately when there are no unsaved changes", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find(".notes-cancel").trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
    expect(w.text()).not.toContain("Änderungen verwerfen?");
  });

  it("shows a server error inline and keeps the dialog open with the typed text", async () => {
    const w = mountDialog({ value: "abc", error: "Speichern fehlgeschlagen." });
    await w.find("textarea").setValue("abc neu");
    expect(w.find('[role="alert"]').text()).toContain("Speichern fehlgeschlagen.");
    expect(w.find("textarea").element.value).toBe("abc neu");
  });

  it("emits null when the trimmed draft is empty", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("   ");
    await w.find(".notes-save").trigger("click");
    expect(w.emitted("save")).toEqual([[null]]);
  });
});
