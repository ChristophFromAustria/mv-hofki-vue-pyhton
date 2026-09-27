import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import CategoryPickDialog from "../../src/frontend/src/components/CategoryPickDialog.vue";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

const categories = [{ id: 1, label: "Deko" }, { id: 2, label: "Fest" }];

describe("CategoryPickDialog", () => {
  it("confirms the chosen ids; the confirm button needs a choice", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "add", categories } });
    expect(w.find("h2").text()).toBe("Kategorien hinzufügen");
    const confirm = w.find(".dialog-confirm");
    expect(confirm.attributes("disabled")).toBeDefined();
    await w.findAll('input[type="checkbox"]')[1].setValue(true);
    await confirm.trigger("click");
    expect(w.emitted("confirm")).toEqual([[[2]]]);
  });

  it("uses remove wording and cancels", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "remove", categories } });
    expect(w.find("h2").text()).toBe("Kategorien entfernen");
    expect(w.find(".dialog-confirm").text()).toBe("Entfernen");
    await w.find(".dialog-cancel").trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("resets the choice when reopened", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "add", categories } });
    await w.findAll('input[type="checkbox"]')[0].setValue(true);
    await w.setProps({ open: false });
    await w.setProps({ open: true });
    expect(w.findAll('input[type="checkbox"]').map((b) => b.element.checked)).toEqual([false, false]);
  });
});
