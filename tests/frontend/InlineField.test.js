import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import InlineField from "../../src/frontend/src/components/InlineField.vue";

function mountField(props) {
  return mount(InlineField, {
    props: { fieldKey: "f", label: "Seriennummer", type: "text", value: "S-1", ...props },
    attachTo: document.body,
  });
}

describe("InlineField display", () => {
  it("shows dt/dd, value and a named edit button", async () => {
    const w = mountField({});
    expect(w.find("dt").text()).toBe("Seriennummer");
    expect(w.find("dd").text()).toContain("S-1");
    const btn = w.find('button[aria-label="„Seriennummer“ bearbeiten"]');
    await btn.trigger("click");
    expect(w.emitted("start")).toHaveLength(1);
  });

  it("formats empty, bool, select, multiselect, date and money", () => {
    expect(mountField({ value: null }).find("dd").text()).toContain("—");
    expect(mountField({ type: "bool", value: true }).find("dd").text()).toContain("Ja");
    const opts = [{ value: 1, label: "Tuba" }, { value: 2, label: "Horn" }];
    expect(mountField({ type: "select", value: 2, options: opts }).find("dd").text()).toContain("Horn");
    expect(mountField({ type: "multiselect", value: [1, 2], options: opts }).find("dd").text()).toContain("Tuba, Horn");
    expect(mountField({ type: "date", value: "2026-03-01" }).find("dd").text()).toContain("01.03.2026");
    const money = mountField({
      type: "money",
      value: { amount: 1250, currency_id: 3 },
      currencies: [{ id: 3, abbreviation: "€" }],
    });
    expect(money.find("dd").text()).toContain(
      `${(1250).toLocaleString("de-AT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`,
    );
  });

  it("shows saving and saved states via a persistent [role=status] announcement", () => {
    const idle = mountField({});
    expect(idle.find('[role="status"]').text()).toBe("");

    const saving = mountField({ saving: true });
    expect(saving.find('[role="status"]').text()).toBe("Speichert …");

    const saved = mountField({ saved: true });
    expect(saved.find('[role="status"]').text()).toBe("Gespeichert");
  });

  it("textarea display gets the text-pre-line class for multi-line values", () => {
    const w = mountField({ type: "textarea", value: "Zeile 1\nZeile 2" });
    expect(w.find(".inline-value").classes()).toContain("text-pre-line");
    expect(mountField({ type: "text" }).find(".inline-value").classes()).not.toContain(
      "text-pre-line",
    );
  });
});

describe("InlineField editing", () => {
  it("text: focuses, saves on Enter, cancels on Escape", async () => {
    const w = mountField({ editing: true });
    await nextTick();
    const input = w.find("input");
    expect(document.activeElement).toBe(input.element);
    await input.setValue("S-2");
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("save")).toEqual([["S-2"]]);
    await input.trigger("keydown", { key: "Escape" });
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("Enter on the Abbrechen button does not save (buttons handle Enter natively)", async () => {
    const w = mountField({ editing: true });
    await nextTick();
    await w.find(".inline-cancel").trigger("keydown", { key: "Enter" });
    expect(w.emitted("save")).toBeUndefined();
  });

  it("Enter on the Speichern button still saves, exactly once", async () => {
    const w = mountField({ editing: true });
    await nextTick();
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toHaveLength(1);
  });

  it("Escape cancels even when focus is on the Speichern or Abbrechen button", async () => {
    const w = mountField({ editing: true });
    await nextTick();
    await w.find(".inline-save").trigger("keydown", { key: "Escape" });
    expect(w.emitted("cancel")).toHaveLength(1);

    const w2 = mountField({ editing: true });
    await nextTick();
    await w2.find(".inline-cancel").trigger("keydown", { key: "Escape" });
    expect(w2.emitted("cancel")).toHaveLength(1);
  });

  it("does not steal focus on initial mount, only returns it after a real editing end", async () => {
    const w = mountField({ editing: false });
    await nextTick();
    await nextTick();
    const btn = w.find('button[aria-label="„Seriennummer“ bearbeiten"]');
    expect(document.activeElement).not.toBe(btn.element);

    await w.setProps({ editing: true });
    await nextTick();
    await nextTick();
    const input = w.find("input");
    expect(document.activeElement).toBe(input.element);

    await w.setProps({ editing: false });
    await nextTick();
    await nextTick();
    // v-if re-creates the button DOM node when leaving edit mode, so re-query
    // it rather than reuse the (now detached) reference from before editing.
    const btnAfter = w.find('button[aria-label="„Seriennummer“ bearbeiten"]');
    expect(document.activeElement).toBe(btnAfter.element);
  });

  it("empty optional text saves null; required shows Pflichtfeld", async () => {
    const w = mountField({ editing: true });
    await w.find("input").setValue("  ");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[null]]);
    const r = mountField({ editing: true, required: true });
    await r.find("input").setValue("");
    await r.find(".inline-save").trigger("click");
    expect(r.emitted("save")).toBeUndefined();
    expect(r.find('[role="alert"]').text()).toBe("Pflichtfeld");
  });

  it("textarea: Enter adds a line, Ctrl+Enter saves", async () => {
    const w = mountField({ type: "textarea", value: "a", editing: true });
    const ta = w.find("textarea");
    await ta.setValue("a\nb");
    await ta.trigger("keydown", { key: "Enter" });
    expect(w.emitted("save")).toBeUndefined();
    await ta.trigger("keydown", { key: "Enter", ctrlKey: true });
    expect(w.emitted("save")).toEqual([["a\nb"]]);
  });

  it("number: integer checks with min/max", async () => {
    const w = mountField({ type: "number", value: 1, min: 1, max: 5, editing: true, required: true });
    const input = w.find("input");
    await input.setValue("0");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Mindestens 1");
    await input.setValue("6");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Höchstens 5");
    await input.setValue("2.5");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Bitte eine ganze Zahl eingeben.");
    await input.setValue("3");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[3]]);
  });

  it("select with empty option for optional fields", async () => {
    const opts = [{ value: 1, label: "Marsch" }];
    const w = mountField({ type: "select", value: 1, options: opts, editing: true });
    expect(w.findAll("option").map((o) => o.text())).toEqual(["—", "Marsch"]);
    await w.find("select").setValue("");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[null]]);
  });

  it("select: saves the option's own value type (number, not string)", async () => {
    const opts = [{ value: 1, label: "Marsch" }, { value: 2, label: "Walzer" }];
    const w = mountField({ type: "select", value: 1, options: opts, editing: true });
    await w.find("select").setValue("2");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[2]]);
    expect(typeof w.emitted("save")[0][0]).toBe("number");
  });

  it("tags: renders a TagSelect and saves the selected ids", async () => {
    const opts = [{ value: 9, label: "Deko" }];
    const w = mountField({ type: "tags", value: [], options: opts, editing: true });
    const input = w.find('[role="combobox"]');
    expect(input.exists()).toBe(true);

    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[[]]]);

    await input.setValue("deko");
    await input.trigger("keydown", { key: "Enter" });
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")[1]).toEqual([[9]]);
  });

  it("bool, multiselect and money", async () => {
    const b = mountField({ type: "bool", value: false, editing: true });
    await b.find('input[type="checkbox"]').setValue(true);
    await b.find(".inline-save").trigger("click");
    expect(b.emitted("save")).toEqual([[true]]);

    const opts = [{ value: 1, label: "Tuba" }, { value: 2, label: "Horn" }];
    const m = mountField({ type: "multiselect", value: [1], options: opts, editing: true });
    await m.findAll('input[type="checkbox"]')[1].setValue(true);
    await m.find(".inline-save").trigger("click");
    expect(m.emitted("save")).toEqual([[[1, 2]]]);

    const cur = [{ id: 3, abbreviation: "€" }];
    const money = mountField({ type: "money", value: { amount: null, currency_id: null }, currencies: cur, editing: true });
    await money.find('input[type="number"]').setValue("12.5");
    await money.find(".inline-save").trigger("click");
    expect(money.find('[role="alert"]').text()).toBe("Bitte eine Währung wählen.");
    await money.find("select").setValue("3");
    await money.find(".inline-save").trigger("click");
    expect(money.emitted("save")).toEqual([[{ amount: 12.5, currency_id: 3 }]]);
  });

  it("money: preselects defaultCurrencyId when the value has none yet", async () => {
    const cur = [{ id: 3, abbreviation: "€" }];
    const w = mountField({
      type: "money",
      value: { amount: null, currency_id: null },
      currencies: cur,
      defaultCurrencyId: 3,
      editing: true,
    });
    await nextTick();
    expect(w.find("select").element.value).toBe("3");
    await w.find('input[type="number"]').setValue("5");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[{ amount: 5, currency_id: 3 }]]);
  });

  it("money: does not override an existing currency_id with defaultCurrencyId", async () => {
    const cur = [
      { id: 1, abbreviation: "$" },
      { id: 3, abbreviation: "€" },
    ];
    const w = mountField({
      type: "money",
      value: { amount: 10, currency_id: 1 },
      currencies: cur,
      defaultCurrencyId: 3,
      editing: true,
    });
    await nextTick();
    expect(w.find("select").element.value).toBe("1");
  });

  it("shows a server error and keeps the typed value", async () => {
    const w = mountField({ editing: true, error: "Pflichtfeld: owner" });
    expect(w.find('[role="alert"]').text()).toBe("Pflichtfeld: owner");
    await w.find("input").setValue("neu");
    await w.setProps({ error: "anders" });
    expect(w.find("input").element.value).toBe("neu");
  });
});
