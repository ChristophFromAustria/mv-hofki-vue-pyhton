import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { defineComponent, h, nextTick } from "vue";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
import { get } from "../../src/frontend/src/lib/api.js";
import {
  useListQuery,
  readState,
  writeQuery,
  buildParams,
} from "../../src/frontend/src/composables/useListQuery.js";

const FILTERS = {
  search: { type: "string", default: "", debounce: true },
  is_active: { type: "bool", default: true },
  register_id__in: { type: "list", default: [] },
  currency_id: { type: "number", default: null },
};

describe("pure helpers", () => {
  it("reads defaults, values and the 'alle' marker", () => {
    expect(readState(FILTERS, {})).toEqual({
      search: "",
      is_active: true,
      register_id__in: [],
      currency_id: null,
    });
    expect(
      readState(FILTERS, {
        search: "Maier",
        is_active: "alle",
        register_id__in: "3,5",
        currency_id: "2",
      }),
    ).toEqual({ search: "Maier", is_active: null, register_id__in: ["3", "5"], currency_id: 2 });
    expect(readState(FILTERS, { is_active: "false", currency_id: "x" })).toMatchObject({
      is_active: false,
      currency_id: null,
    });
  });

  it("writes only non-default values; an emptied non-empty default becomes 'alle'", () => {
    const defaults = readState(FILTERS, {});
    expect(writeQuery(FILTERS, defaults, "last_name", "last_name")).toEqual({});
    expect(
      writeQuery(
        FILTERS,
        { search: "Maier", is_active: null, register_id__in: ["3", "5"], currency_id: 2 },
        "-last_name",
        "last_name",
      ),
    ).toEqual({
      search: "Maier",
      is_active: "alle",
      register_id__in: "3,5",
      currency_id: "2",
      order_by: "-last_name",
    });
  });

  it("builds API params in a stable order without empty values", () => {
    const params = buildParams(
      FILTERS,
      { search: " Maier ", is_active: null, register_id__in: ["3", "5"], currency_id: null },
      { sort: "last_name", base: { category: "x" }, offset: 50, limit: 50 },
    );
    expect(params.toString()).toBe(
      "category=x&search=Maier&register_id__in=3%2C5&order_by=last_name&limit=50&offset=50",
    );
  });
});

async function setup(query = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: { render: () => null } }],
  });
  router.push({ path: "/", query });
  await router.isReady();
  let list;
  const Host = defineComponent({
    setup() {
      list = useListQuery({
        endpoint: "/musicians",
        filters: FILTERS,
        defaultSort: "last_name",
        pageSize: 2,
      });
      return () => h("div");
    },
  });
  mounted.push(mount(Host, { global: { plugins: [router] } }));
  await flushPromises();
  return { list, router };
}

const mounted = [];

const page = (ids, total) => ({ items: ids.map((id) => ({ id })), total });

describe("useListQuery", () => {
  beforeEach(() => get.mockReset());
  afterEach(() => {
    // Unmounting disposes the scope, so no debounce timer fires into the next test.
    mounted.splice(0).forEach((w) => w.unmount());
    vi.useRealTimers();
  });

  it("loads the first page from the URL state", async () => {
    get.mockResolvedValue(page([1, 2], 3));
    const { list } = await setup({ register_id__in: "3" });
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith(
      "/musicians?is_active=true&register_id__in=3&order_by=last_name&limit=2&offset=0",
    );
    expect(list.items.value.map((i) => i.id)).toEqual([1, 2]);
    expect(list.hasMore.value).toBe(true);
    expect(list.activeFilterCount.value).toBe(1);
  });

  it("loadMore appends and stops at total", async () => {
    get.mockResolvedValueOnce(page([1, 2], 3)).mockResolvedValueOnce(page([3], 3));
    const { list } = await setup();
    await list.loadMore();
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?is_active=true&order_by=last_name&limit=2&offset=2",
    );
    expect(list.items.value.map((i) => i.id)).toEqual([1, 2, 3]);
    expect(list.hasMore.value).toBe(false);
    await list.loadMore();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("a filter change resets the list and writes the URL without a second request", async () => {
    get.mockResolvedValue(page([1, 2], 3));
    const { list, router } = await setup();
    list.setFilter("is_active", false);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ is_active: "false" });
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?is_active=false&order_by=last_name&limit=2&offset=0",
    );
  });

  it("setFilter coerces raw values to the filter type", async () => {
    get.mockResolvedValue(page([], 0));
    const { list } = await setup();
    list.setFilter("currency_id", "4");
    list.setFilter("register_id__in", ["2"]);
    expect(list.state.currency_id).toBe(4);
    list.setFilter("currency_id", "");
    expect(list.state.currency_id).toBe(null);
  });

  it("debounces search", async () => {
    get.mockResolvedValue(page([], 0));
    const { list } = await setup();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    list.state.search = "Ma";
    await nextTick();
    list.state.search = "Mai";
    await nextTick();
    await vi.advanceTimersByTimeAsync(299);
    expect(get).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?search=Mai&is_active=true&order_by=last_name&limit=2&offset=0",
    );
  });

  it("drops a stale response", async () => {
    get.mockResolvedValueOnce(page([1], 1));
    const { list } = await setup();
    let resolveSlow;
    get
      .mockImplementationOnce(() => new Promise((r) => (resolveSlow = r)))
      .mockResolvedValueOnce(page([9], 1));
    list.setFilter("is_active", false);
    await nextTick();
    list.setFilter("is_active", null);
    await flushPromises();
    resolveSlow(page([7], 1));
    await flushPromises();
    expect(list.items.value.map((i) => i.id)).toEqual([9]);
    expect(list.loading.value).toBe(false);
  });

  it("applies external URL changes (back button)", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup();
    await router.replace({ query: { is_active: "false", order_by: "-last_name" } });
    await flushPromises();
    expect(list.state.is_active).toBe(false);
    expect(list.sort.value).toBe("-last_name");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("keeps the URL in sync when a change is reverted before navigation lands", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup();
    list.setFilter("is_active", false);
    await nextTick();
    list.setFilter("is_active", true);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({});
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?is_active=true&order_by=last_name&limit=2&offset=0",
    );
  });

  it("an external navigation to a previously written query is still applied", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup();
    list.setFilter("is_active", false);
    await flushPromises();
    list.setFilter("is_active", true);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({});
    await router.replace({ query: { is_active: "false" } });
    await flushPromises();
    expect(list.state.is_active).toBe(false);
  });

  it("resetFilters restores defaults and clears the URL", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup({ is_active: "alle", search: "x" });
    list.resetFilters();
    await flushPromises();
    expect(list.state).toMatchObject({ search: "", is_active: true, register_id__in: [] });
    expect(router.currentRoute.value.query).toEqual({});
  });

  it("reset does not fetch twice", async () => {
    get.mockResolvedValue(page([], 0));
    const { list } = await setup({ is_active: "alle", search: "x" });
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    list.resetFilters();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(400);
    await flushPromises();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("keeps loaded items when loading more fails", async () => {
    get.mockResolvedValueOnce(page([1, 2], 3)).mockRejectedValueOnce(new Error("Netz weg"));
    const { list } = await setup();
    await list.loadMore();
    expect(list.error.value).toBe("Netz weg");
    expect(list.items.value).toHaveLength(2);
  });

  it("a failed first load clears items and reports the error", async () => {
    get.mockRejectedValueOnce(new Error("Server nicht erreichbar"));
    const { list } = await setup();
    expect(list.error.value).toBe("Server nicht erreichbar");
    expect(list.items.value).toEqual([]);
    expect(list.loading.value).toBe(false);
  });
});
