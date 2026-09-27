import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import GroupSelect from "../../src/frontend/src/components/GroupSelect.vue";

describe("GroupSelect", () => {
  it("offers 'Keine' plus options and emits the key", async () => {
    const w = mount(GroupSelect, {
      props: { options: [{ key: "type", label: "Typ" }, { key: "status", label: "Status" }], modelValue: "type" },
    });
    expect(w.findAll("option").map((o) => o.text())).toEqual(["Keine", "Typ", "Status"]);
    expect(w.find("select").element.value).toBe("type");
    await w.find("select").setValue("");
    expect(w.emitted("update:modelValue")).toEqual([[""]]);
    expect(w.find("label").text()).toBe("Gruppieren nach");
  });
});
