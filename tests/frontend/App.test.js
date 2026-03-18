import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import App from "../../src/frontend/src/App.vue";
import { createRouter, createMemoryHistory } from "vue-router";
import HomePage from "../../src/frontend/src/pages/HomePage.vue";

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: HomePage }],
  });
}

describe("App", () => {
  it("mounts and renders NavBar", async () => {
    const router = createTestRouter();
    router.push("/");
    await router.isReady();

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    });

    expect(wrapper.find("nav").exists()).toBe(true);
    expect(wrapper.text()).toContain("mv_hofki");
  });
});
