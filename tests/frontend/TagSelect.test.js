import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import TagSelect from "../../src/frontend/src/components/TagSelect.vue";

const options = [
  { id: 1, label: "Deko" },
  { id: 2, label: "Gastro" },
  { id: 3, label: "Küche" },
];

// Mounts TagSelect and keeps v-model in sync like a parent would.
function setup(props = {}) {
  let w;
  w = mount(TagSelect, {
    props: {
      label: "Kategorien",
      options,
      modelValue: [],
      "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }),
      ...props,
    },
    attachTo: document.body,
  });
  return w;
}

function optionTexts(w) {
  return w.findAll('[role="option"]').map((o) => o.text());
}

describe("TagSelect", () => {
  it("shows selected ids as chips with a named remove button", () => {
    const w = setup({ modelValue: [2] });
    expect(w.findAll(".category-chip").map((c) => c.text().replace("✕", "").trim())).toEqual([
      "Gastro",
    ]);
    expect(w.find('button[aria-label="„Gastro“ entfernen"]').exists()).toBe(true);
  });

  it("filters suggestions case-insensitively and hides selected ones", async () => {
    const w = setup({ modelValue: [1] });
    const input = w.find("input");
    await input.trigger("focus");
    expect(optionTexts(w)).toEqual(["Gastro", "Küche"]);
    await input.setValue("KÜ");
    expect(optionTexts(w)).toEqual(["Küche"]);
  });

  it("selects a suggestion with arrow keys and Enter", async () => {
    const w = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[2]]);
  });

  it("selects an exact match with Enter without arrow keys", async () => {
    const w = setup();
    const input = w.find("input");
    await input.setValue("deko");
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[1]]);
  });

  it("removes a chip by button and by Backspace in an empty field", async () => {
    const w = setup({ modelValue: [1, 2] });
    await w.find('button[aria-label="„Deko“ entfernen"]').trigger("click");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[2]]);
    await w.find("input").trigger("keydown", { key: "Backspace" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[]]);
  });

  it("offers creation only without an exact match and only with createOption", async () => {
    const w = setup();
    const input = w.find("input");
    await input.setValue("Licht");
    expect(optionTexts(w)).toEqual([]);

    const w2 = setup({ createOption: vi.fn() });
    const input2 = w2.find("input");
    await input2.setValue("Licht");
    expect(optionTexts(w2)).toEqual(["„Licht“ als neue Kategorie anlegen"]);
    await input2.setValue("gastro");
    expect(optionTexts(w2)).toEqual(["Gastro"]);
  });

  it("creates a trimmed new category and selects it", async () => {
    const createOption = vi.fn().mockResolvedValue({ id: 9, label: "Technik" });
    const w = setup({ createOption });
    const input = w.find("input");
    await input.setValue("  Technik ");
    await input.trigger("keydown", { key: "Enter" });
    await new Promise((r) => setTimeout(r, 0));
    expect(createOption).toHaveBeenCalledWith("Technik");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[9]]);
    expect(input.element.value).toBe("");
  });

  it("shows an inline error when creation fails", async () => {
    const createOption = vi.fn().mockRejectedValue(new Error("Kategorie existiert bereits"));
    const w = setup({ createOption });
    const input = w.find("input");
    await input.setValue("Technik");
    await input.trigger("keydown", { key: "Enter" });
    await new Promise((r) => setTimeout(r, 0));
    expect(w.find('[role="alert"]').text()).toBe("Kategorie existiert bereits");
    expect(w.emitted("update:modelValue")).toBeUndefined();
  });

  it("does not submit the surrounding form on Enter while typing", async () => {
    const onSubmit = vi.fn((e) => e.preventDefault());
    const Host = {
      components: { TagSelect },
      template: `<form @submit="onSubmit"><TagSelect label="Kategorien" :options="options" :model-value="[]" /></form>`,
      setup: () => ({ onSubmit, options }),
    };
    const w = mount(Host, { attachTo: document.body });
    const input = w.find("input");
    await input.setValue("Lic");
    const ev = new KeyboardEvent("keydown", { key: "Enter", cancelable: true, bubbles: true });
    input.element.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
  });

  it("closes the list on Escape and wires ARIA", async () => {
    const w = setup();
    const input = w.find("input");
    await input.trigger("focus");
    expect(input.attributes("role")).toBe("combobox");
    expect(input.attributes("aria-expanded")).toBe("true");
    await input.trigger("keydown", { key: "Escape" });
    expect(input.attributes("aria-expanded")).toBe("false");
  });
});
