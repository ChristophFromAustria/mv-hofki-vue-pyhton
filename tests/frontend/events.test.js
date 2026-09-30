import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import {
  actorLabel,
  eventChanges,
  eventHeadline,
  eventLink,
  formatEventTime,
} from "../../src/frontend/src/lib/events.js";
import EventList from "../../src/frontend/src/components/EventList.vue";

const base = { id: 1, at: "2026-09-30T12:02:00Z", actor: null, source: "web", entity_id: 7, entity_label: "TR-0006 Trompete", item_id: 7, musician_id: null, changes: null, summary: null };

describe("events", () => {
  it("names who did it", () => {
    expect(actorLabel({ ...base, actor: "a@b.at" })).toBe("a@b.at");
    expect(actorLabel({ ...base, source: "ki-import" })).toBe("KI-Import");
    expect(actorLabel({ ...base, source: "system" })).toBe("System");
    expect(actorLabel(base)).toBe("unbekannt");
  });

  it("shows UTC times in local de-AT form", () => {
    const expected = new Date("2026-09-30T12:02:00Z").toLocaleString("de-AT", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
    expect(formatEventTime(base.at)).toBe(expected);
  });

  it("words the headline", () => {
    expect(eventHeadline({ ...base, entity_type: "item", action: "updated" })).toBe("Gegenstand geändert");
    expect(eventHeadline({ ...base, entity_type: "loan", action: "loaned" })).toBe("Ausgeliehen");
    expect(eventHeadline({ ...base, entity_type: "loan", action: "updated" })).toBe("Leihe geändert");
    expect(eventHeadline({ ...base, entity_type: "musician", action: "created" })).toBe("Musiker angelegt");
  });

  it("links to the record, not to deleted ones", () => {
    expect(eventLink({ ...base, entity_type: "item", action: "updated" })).toBe("/inventar/7");
    expect(eventLink({ ...base, entity_type: "loan", action: "loaned" })).toBe("/inventar/7");
    expect(eventLink({ ...base, entity_type: "musician", action: "updated", entity_id: 3, item_id: null })).toBe("/musiker/3");
    expect(eventLink({ ...base, entity_type: "register", action: "created", item_id: null })).toBe("/einstellungen/register");
    expect(eventLink({ ...base, entity_type: "item", action: "deleted" })).toBeNull();
  });

  it("formats changes with — for empty values", () => {
    const [c] = eventChanges({ ...base, changes: [{ field: "x", label: "Lagerort", old: null, new: "Schrank" }] });
    expect(c).toMatchObject({ label: "Lagerort", old: "—", new: "Schrank", oldEmpty: true, long: false });
  });

  it("EventList renders when, who, what and old → new", () => {
    const w = mount(EventList, {
      props: { events: [{ ...base, entity_type: "item", action: "updated", actor: "a@b.at", changes: [{ field: "manufacturer", label: "Hersteller", old: "Yamaha", new: "Bach" }] }] },
      global: { stubs: { RouterLink: { props: ["to"], template: "<a :href='to'><slot /></a>" } } },
    });
    expect(w.text()).toContain("a@b.at");
    expect(w.text()).toContain("Gegenstand geändert");
    expect(w.find("a").attributes("href")).toBe("/inventar/7");
    expect(w.find(".event-changes").text()).toContain("Hersteller:");
    expect(w.find(".event-old").text()).toBe("Yamaha");
    expect(w.find(".event-new").text()).toBe("Bach");
  });
});
