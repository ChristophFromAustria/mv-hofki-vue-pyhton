import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BulkCategoryBar from "../../src/frontend/src/components/BulkCategoryBar.vue";

describe("BulkCategoryBar", () => {
  it("shows the count and emits actions", async () => {
    const w = mount(BulkCategoryBar, { props: { count: 3 } });
    expect(w.text()).toContain("3 ausgewählt");
    const buttons = Object.fromEntries(w.findAll("button").map((b) => [b.text(), b]));
    await buttons["Alle geladenen auswählen"].trigger("click");
    await buttons["Kategorien hinzufügen"].trigger("click");
    await buttons["Kategorien entfernen"].trigger("click");
    await buttons["Fertig"].trigger("click");
    expect(Object.keys(w.emitted())).toEqual(expect.arrayContaining(["select-all", "add", "remove", "done"]));
  });

  it("disables actions without selection or while busy and shows status", () => {
    const empty = mount(BulkCategoryBar, { props: { count: 0 } });
    const add = empty.findAll("button").find((b) => b.text() === "Kategorien hinzufügen");
    expect(add.attributes("disabled")).toBeDefined();
    const busy = mount(BulkCategoryBar, { props: { count: 2, busy: true, message: "Wird gespeichert …" } });
    expect(busy.findAll("button").find((b) => b.text() === "Kategorien entfernen").attributes("disabled")).toBeDefined();
    expect(busy.find('[role="status"]').text()).toBe("Wird gespeichert …");
    const err = mount(BulkCategoryBar, { props: { count: 2, error: "Netz weg" } });
    expect(err.find('[role="alert"]').text()).toBe("Netz weg");
  });
});
