import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import InfiniteLoader from "../../src/frontend/src/components/InfiniteLoader.vue";

afterEach(() => vi.unstubAllGlobals());

describe("InfiniteLoader", () => {
  it("shows the count and a fallback button", async () => {
    const w = mount(InfiniteLoader, { props: { hasMore: true, count: 50, total: 157 } });
    expect(w.text()).toContain("50 von 157");
    await w.find("button").trigger("click");
    expect(w.emitted("load-more")).toHaveLength(1);
  });

  it("shows loading and hides the button", () => {
    const w = mount(InfiniteLoader, {
      props: { hasMore: true, loading: true, count: 50, total: 157 },
    });
    expect(w.text()).toContain("Wird geladen …");
    expect(w.find("button").exists()).toBe(false);
  });

  it("shows an error with retry", async () => {
    const w = mount(InfiniteLoader, {
      props: { hasMore: true, error: "Netz weg", count: 50, total: 157 },
    });
    expect(w.find('[role="alert"]').text()).toContain("Netz weg");
    await w.find("button").trigger("click");
    expect(w.emitted("load-more")).toHaveLength(1);
  });

  it("emits when the sentinel becomes visible, and again after loading if still visible", async () => {
    let callback;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb) {
          callback = cb;
        }
        observe() {}
        disconnect() {}
      },
    );
    const w = mount(InfiniteLoader, { props: { hasMore: true, count: 2, total: 9 } });
    callback([{ isIntersecting: true }]);
    expect(w.emitted("load-more")).toHaveLength(1);
    await w.setProps({ loading: true });
    await w.setProps({ loading: false });
    await nextTick();
    expect(w.emitted("load-more")).toHaveLength(2);
  });

  it("renders nothing but the sentinel for an empty list", () => {
    const w = mount(InfiniteLoader, { props: { hasMore: false, count: 0, total: 0 } });
    expect(w.text()).toBe("");
  });
});
