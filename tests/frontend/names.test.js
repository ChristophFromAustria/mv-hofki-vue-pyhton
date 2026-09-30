import { describe, it, expect } from "vitest";
import { guessName } from "../../src/frontend/src/lib/names.js";

describe("guessName", () => {
  it("splits what was typed into first and last name", () => {
    expect(guessName("Anna Maier")).toEqual({ first_name: "Anna", last_name: "Maier" });
    expect(guessName("Maier, Anna")).toEqual({ first_name: "Anna", last_name: "Maier" });
    expect(guessName("  Anna   von  Berg ")).toEqual({ first_name: "Anna", last_name: "von Berg" });
    expect(guessName("Maier")).toEqual({ first_name: "", last_name: "Maier" });
    expect(guessName("")).toEqual({ first_name: "", last_name: "" });
  });
});
