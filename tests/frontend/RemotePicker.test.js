import { describe, it, expect, vi, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import RemotePicker from "../../src/frontend/src/components/RemotePicker.vue";

const OPTIONS = [
  { id: 1, label: "Maier Anna", description: "" },
  { id: 2, label: "Huber Carl", description: "extern" },
];

function setup(props = {}) {
  let w;
  const fetchOptions = props.fetchOptions || vi.fn().mockResolvedValue(OPTIONS);
  w = mount(RemotePicker, {
    props: {
      label: "Musiker",
      modelValue: null,
      fetchOptions,
      debounceMs: 0,
      "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }),
      ...props,
    },
    attachTo: document.body,
  });
  return { w, fetchOptions };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => (document.body.innerHTML = ""));

describe("RemotePicker", () => {
  it("fetches on focus and shows options", async () => {
    const { w, fetchOptions } = setup();
    await w.find("input").trigger("focus");
    await tick();
    await flushPromises();
    expect(fetchOptions).toHaveBeenCalledWith("");
    expect(w.findAll('[role="option"]').map((o) => o.text())).toEqual([
      "Maier Anna",
      "Huber Carlextern",
    ]);
  });

  it("debounces typing and passes the trimmed text", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const fetchOptions = vi.fn().mockResolvedValue(OPTIONS);
    const { w } = setup({ fetchOptions, debounceMs: 250 });
    const input = w.find("input");
    await input.setValue("Ma");
    await input.setValue("Mai ");
    await vi.advanceTimersByTimeAsync(249);
    expect(fetchOptions).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchOptions).toHaveBeenCalledTimes(1);
    expect(fetchOptions).toHaveBeenCalledWith("Mai");
    vi.useRealTimers();
  });

  it("selects with keyboard and shows the label", async () => {
    const { w } = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await tick();
    await flushPromises();
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([2]);
    expect(w.emitted("select").at(-1)[0]).toMatchObject({ id: 2 });
    expect(input.element.value).toBe("Huber Carl");
    expect(input.attributes("aria-expanded")).toBe("false");
  });

  it("typing after a selection clears it; the clear button empties", async () => {
    const { w } = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await tick();
    await flushPromises();
    await w.findAll('[role="option"]')[0].trigger("click");
    await w.find('button[aria-label="Auswahl entfernen"]').trigger("click");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([null]);
    expect(input.element.value).toBe("");
  });

  it("shows 'Keine Treffer' and errors", async () => {
    const empty = setup({ fetchOptions: vi.fn().mockResolvedValue([]) });
    await empty.w.find("input").setValue("zzz");
    await tick();
    await flushPromises();
    expect(empty.w.text()).toContain("Keine Treffer");

    const failing = setup({ fetchOptions: vi.fn().mockRejectedValue(new Error("Netz weg")) });
    await failing.w.find("input").setValue("a");
    await tick();
    await flushPromises();
    expect(failing.w.find('[role="alert"]').text()).toBe("Netz weg");
  });

  it("shows selectedLabel for an externally set value and clears on null", async () => {
    const { w } = setup({ modelValue: 5, selectedLabel: "Aigner Dora" });
    expect(w.find("input").element.value).toBe("Aigner Dora");
    await w.setProps({ modelValue: null });
    expect(w.find("input").element.value).toBe("");
  });
});

describe("RemotePicker scopes", () => {
  const scopes = [
    { value: "active", label: "Nur aktive" },
    { value: "all", label: "Alle" },
  ];

  it("passes the scope to fetchOptions and re-searches when it changes", async () => {
    const { w, fetchOptions } = setup({ scopes });
    await w.find("input").trigger("focus");
    await tick();
    await flushPromises();
    expect(fetchOptions).toHaveBeenLastCalledWith("", { scope: "active" });
    const buttons = w.findAll(".remote-picker-scopes button");
    expect(buttons.map((b) => b.text())).toEqual(["Nur aktive", "Alle"]);
    expect(buttons[0].attributes("aria-pressed")).toBe("true");
    await w.find("input").setValue("mai");
    await buttons[1].trigger("click");
    await flushPromises();
    expect(fetchOptions).toHaveBeenLastCalledWith("mai", { scope: "all" });
    expect(buttons[1].attributes("aria-pressed")).toBe("true");
  });

  it("starts with defaultScope and calls fetchOptions with the text only without scopes", async () => {
    const { w, fetchOptions } = setup({ scopes, defaultScope: "all" });
    await w.find("input").trigger("focus");
    await tick();
    await flushPromises();
    expect(fetchOptions).toHaveBeenLastCalledWith("", { scope: "all" });
    const plain = setup();
    await plain.w.find("input").trigger("focus");
    await tick();
    await flushPromises();
    expect(plain.fetchOptions).toHaveBeenLastCalledWith("");
    expect(plain.w.find(".remote-picker-scopes").exists()).toBe(false);
  });
});
