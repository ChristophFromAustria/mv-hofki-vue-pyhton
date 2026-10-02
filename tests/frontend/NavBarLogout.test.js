import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
vi.mock("vue-router", () => ({
  RouterLink: { props: ["to"], template: "<a :href='to'><slot /></a>" },
  useRouter: () => ({ push: vi.fn() }),
}));
import { get } from "../../src/frontend/src/lib/api.js";
import NavBar from "../../src/frontend/src/components/NavBar.vue";

beforeAll(() => {
  // jsdom has no matchMedia (theme detection in NavBar).
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
});

// Block body: a value returned from beforeEach is called as teardown.
beforeEach(() => {
  get.mockReset();
});

function mountNav() {
  return mount(NavBar, { global: { stubs: { GlobalSearch: true } } });
}

describe("NavBar logout", () => {
  it("offers Abmelden with the Cloudflare Access logout when signed in", async () => {
    get.mockResolvedValue({ email: "zeugwart@mv-hofkirchen.at" });
    const w = mountNav();
    await flushPromises();
    expect(w.find(".account-email").text()).toBe("zeugwart@mv-hofkirchen.at");
    expect(w.find(".account-logout").attributes("href")).toBe("/cdn-cgi/access/logout");
  });

  it("shows nothing without Cloudflare (local use)", async () => {
    get.mockResolvedValue({ email: null });
    const w = mountNav();
    await flushPromises();
    expect(w.find(".account").exists()).toBe(false);
  });
});
