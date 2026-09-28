import { describe, it, expect } from "vitest";
import { musicianFieldDefs } from "../../src/frontend/src/lib/musicianFields.js";

const regs = [{ id: 1, label: "Tuba" }, { id: 2, label: "Horn" }];

describe("musicianFieldDefs", () => {
  it("groups fields into membership and contact", () => {
    const d = musicianFieldDefs(regs);
    expect(d.membership.map((f) => f.key)).toEqual(["is_active", "registers", "is_extern", "notes"]);
    expect(d.contact.map((f) => f.key)).toEqual([
      "first_name", "last_name", "phone", "email", "street_address", "postal_code", "city",
    ]);
  });

  it("maps registers and postal code", () => {
    const d = musicianFieldDefs(regs);
    const reg = d.membership.find((f) => f.key === "registers");
    expect(reg.type).toBe("multiselect");
    expect(reg.options).toEqual([{ value: 1, label: "Tuba" }, { value: 2, label: "Horn" }]);
    expect(reg.value({ registers: [{ id: 2, label: "Horn" }] })).toEqual([2]);
    expect(reg.toPatch([1, 2])).toEqual({ register_ids: [1, 2] });
    const plz = d.contact.find((f) => f.key === "postal_code");
    expect(plz.type).toBe("number");
    expect(d.contact.find((f) => f.key === "first_name").required).toBe(true);
    expect(d.membership.find((f) => f.key === "is_active").label).toBe("Status");
  });
});
