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
    await w.findAll("button").find((b) => b.text() === "Vorschau").trigger("click");
    expect(w.find("textarea").exists()).toBe(false);
    expect(w.find(".markdown-text").html()).toContain("<strong>fett</strong>");
    await w.findAll("button").find((b) => b.text() === "Bearbeiten").trigger("click");
    expect(w.find("textarea").exists()).toBe(true);
  });

  it("counter warns near the limit and disables save over it", async () => {
    const w = mountDialog({ value: "123456789", maxLength: 10 });
    await nextTick();
    expect(w.find("[aria-live='polite']").text()).toContain("9");
    expect(w.find("[aria-live='polite']").text()).toContain("10");
    expect(w.find(".notes-counter").classes()).toContain("is-warning");
    await w.find("textarea").setValue("12345678901");
    await nextTick();
    expect(w.find('[role="alert"]').text()).toContain("Höchstens 10 Zeichen");
    expect(w.find(".notes-counter").classes()).toContain("is-danger");
    expect(w.find(".notes-save").attributes("disabled")).toBeDefined();
  });

  it("saves on Ctrl+Enter", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find("textarea").trigger("keydown", { key: "Enter", ctrlKey: true });
    expect(w.emitted("save")).toEqual([["abc def"]]);
  });

  it("does not save on Ctrl+Enter while the discard-confirm panel is shown", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find(".notes-cancel").trigger("click");
    expect(w.text()).toContain("Änderungen verwerfen?");
    await w.find("dialog").trigger("keydown", { key: "Enter", ctrlKey: true });
    expect(w.emitted("save")).toBeUndefined();
  });

  it("shows Speichert … and disables Speichern while saving", () => {
    const w = mountDialog({ value: "abc", saving: true });
    expect(w.find(".notes-save").text()).toBe("Speichert …");
    expect(w.find(".notes-save").attributes("disabled")).toBeDefined();
  });

  it("asks to discard unsaved changes on Abbrechen, and can resume editing", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find(".notes-cancel").trigger("click");
    expect(w.text()).toContain("Änderungen verwerfen?");
    expect(w.emitted("cancel")).toBeUndefined();

    const weiter = w.findAll("button").find((b) => b.text() === "Weiter bearbeiten");
    await weiter.trigger("click");
    expect(w.find("textarea").element.value).toBe("abc def");

    await w.find(".notes-cancel").trigger("click");
    const verwerfen = w.findAll("button").find((b) => b.text() === "Verwerfen");
    await verwerfen.trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("the discard-confirm panel is an alertdialog labelled by its own text, focusing Weiter bearbeiten", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find("textarea").setValue("abc def");
    await w.find(".notes-cancel").trigger("click");
    await nextTick();
    const panel = w.find('[role="alertdialog"]');
    expect(panel.exists()).toBe(true);
    const labelId = panel.attributes("aria-labelledby");
    expect(w.find(`#${labelId}`).text()).toBe("Änderungen verwerfen?");
    const weiter = w.findAll("button").find((b) => b.text() === "Weiter bearbeiten");
    expect(document.activeElement).toBe(weiter.element);
  });

  it("cancels immediately when there are no unsaved changes", async () => {
    const w = mountDialog({ value: "abc" });
    await w.find(".notes-cancel").trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
    expect(w.text()).not.toContain("Änderungen verwerfen?");
  });

  it("the native cancel event (Escape) behaves like the Abbrechen button", async () => {
    const clean = mountDialog({ value: "abc" });
    await clean.find("dialog").trigger("cancel");
    expect(clean.emitted("cancel")).toHaveLength(1);

    const dirty = mountDialog({ value: "abc" });
    await dirty.find("textarea").setValue("abc def");
    await dirty.find("dialog").trigger("cancel");
    expect(dirty.emitted("cancel")).toBeUndefined();
    expect(dirty.text()).toContain("Änderungen verwerfen?");
  });

  it("a forced native close (second Escape, no cancel) reopens with the discard panel when dirty, or just cancels when clean", async () => {
    const clean = mountDialog({ value: "abc" });
    const cleanDialogEl = clean.find("dialog").element;
    cleanDialogEl.close();
    cleanDialogEl.dispatchEvent(new Event("close"));
    expect(clean.emitted("cancel")).toHaveLength(1);

    const dirty = mountDialog({ value: "abc" });
    await dirty.find("textarea").setValue("abc def");
    const dirtyDialogEl = dirty.find("dialog").element;
    dirtyDialogEl.close();
    dirtyDialogEl.dispatchEvent(new Event("close"));
    await nextTick();
    expect(dirty.emitted("cancel")).toBeUndefined();
    expect(dirty.text()).toContain("Änderungen verwerfen?");
    expect(dirtyDialogEl.hasAttribute("open")).toBe(true);
  });

  it("returning to Bearbeiten from Vorschau focuses the textarea", async () => {
    const w = mountDialog({ value: "abc" });
    await w.findAll("button").find((b) => b.text() === "Vorschau").trigger("click");
    await w.findAll("button").find((b) => b.text() === "Bearbeiten").trigger("click");
    await nextTick();
    expect(document.activeElement).toBe(w.find("textarea").element);
  });

  it("the Bearbeiten/Vorschau toggle exposes aria-pressed and no redundant aria-label", async () => {
    const w = mountDialog({ value: "abc" });
    const edit = w.findAll("button").find((b) => b.text() === "Bearbeiten");
    const preview = w.findAll("button").find((b) => b.text() === "Vorschau");
    expect(edit.attributes("aria-pressed")).toBe("true");
    expect(edit.attributes("aria-label")).toBeUndefined();
    expect(preview.attributes("aria-pressed")).toBe("false");
    expect(preview.attributes("aria-label")).toBeUndefined();
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
