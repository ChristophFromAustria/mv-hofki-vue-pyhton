import { describe, it, expect, vi, afterEach } from "vitest";
import { useInlineEdit } from "../../src/frontend/src/composables/useInlineEdit.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("useInlineEdit", () => {
  it("edits one field at a time", () => {
    const e = useInlineEdit(vi.fn());
    e.start("a");
    e.start("b");
    expect(e.editingKey.value).toBe("b");
    e.cancel();
    expect(e.editingKey.value).toBe(null);
  });

  it("commits, closes and flags saved for 2 s", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue({});
    const e = useInlineEdit(save);
    e.start("notes");
    const p = e.commit("notes", { notes: "x" });
    expect(e.savingKey.value).toBe("notes");
    await p;
    expect(save).toHaveBeenCalledWith({ notes: "x" });
    expect(e.editingKey.value).toBe(null);
    expect(e.savedKey.value).toBe("notes");
    vi.advanceTimersByTime(2000);
    expect(e.savedKey.value).toBe(null);
  });

  it("keeps the field open with the error on failure", async () => {
    const e = useInlineEdit(vi.fn().mockRejectedValue(new Error("Pflichtfeld: owner")));
    e.start("owner");
    await e.commit("owner", { owner: "" });
    expect(e.editingKey.value).toBe("owner");
    expect(e.error.value).toBe("Pflichtfeld: owner");
    expect(e.savingKey.value).toBe(null);
    e.start("notes");
    expect(e.error.value).toBe("");
  });
});
