# Detailseiten: Einklappen und Bearbeiten Feld für Feld, Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Item- und Musiker-Detailseiten bekommen einklappbare Abschnitte. Der Zustand gilt pro Abschnitt und Seitentyp und wird gespeichert; eingeklappt zeigt der Kopf eine Kurzinfo.
- Stammdaten lassen sich Feld für Feld direkt auf der Seite bearbeiten.

**Architektur:**
- **Einklappen:** `useSectionCollapse` (localStorage) und `CollapsibleSection` (Disclosure-Kopf mit Kurzinfo und Aktionen-Slot).
- **Bearbeiten:**
  - `useInlineEdit` hält fest, welches Feld gerade bearbeitet wird, und ruft das Speichern auf.
  - `InlineField` rendert `<dt>`/`<dd>` mit dem passenden Eingabefeld je Typ.
  - `lib/itemFields.js` beschreibt die Stammdaten-Felder je Item-Art.
- **Backend:** Das Item-Update liefert 422 statt 500 und schützt Pflichtfelder.

**Tech Stack:** Vue 3.4, Vitest + @vue/test-utils; FastAPI, Pydantic 2, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-28-detail-collapse-inline-edit-design.md`

## Global Constraints

- **Ausführung und Commits wie in den letzten Plänen:**
  - Befehle laufen per `IN_CONTAINER '<befehl>'` = `docker exec -w /workspaces/mv_hofki mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc '<befehl>'`.
  - Commit im Container mit Host-Identität (`-e GIT_AUTHOR_NAME/EMAIL -e GIT_COMMITTER_NAME/EMAIL`), Nachricht endet mit `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
  - Nur eigene Dateien committen; niemals `git stash/reset/clean/add -A`.
- **Sprache und Gestaltung:**
  - Deutsch mit „…“, österreichische Schreibung.
  - Nur Tokens aus `style.css`.
  - Touch-Ziele ≥ 44 px.
  - Benannte Buttons (`aria-label`).
  - Fehler inline, kein `alert()` in neuem Code.
- **Bekannte fremde Testfehler, ignorieren:**
  - `tests/backend/test_item_invoices.py::test_create_invoice_on_sheet_music_rejected`
  - `tests/backend/test_scanner_config.py::test_sync_preserves_user_value`
  - `tests/frontend/App.test.js`
- **Speicherschlüssel:** `detail-collapsed:<scope>:<section>`, gespeichert wird `"1"` = eingeklappt. Standard ist offen. `localStorage` nur in `try/catch`.
- **Texte:**
  - Stift-Button: `aria-label` „„<Label>“ bearbeiten“
  - Buttons beim Bearbeiten: „Speichern“ und „Abbrechen“
  - Status: „Speichert …“ und „Gespeichert“
  - Prüfungen: „Pflichtfeld“, „Bitte eine ganze Zahl eingeben.“, „Mindestens <min>“, „Höchstens <max>“, „Bitte eine Währung wählen.“
- **Anzeige:**
  - leer: „—“
  - Datum: `TT.MM.JJJJ`
  - Geld: `Number(x).toLocaleString("de-AT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + Kürzel`
- **Browser-Prüfungen gegen die echte DB:** Erlaubt ist nur, **ein** Feld an **einem** Item und **einem** Musiker zu ändern und sofort auf den notierten Ursprungswert zurückzusetzen. Danach per API vergleichen, dass alles unverändert ist. Keinen Instrumenten-Typ ändern, denn das vergibt eine neue Nummer.

## Review Focus

1. **Typwechsel mit anderem Kürzel:** Vor dem Speichern kommt der Dialog; bei „Abbrechen“ wird nichts gesendet und das Feld bleibt im Bearbeitungsmodus. (Test in Task 4)
2. **Enter in `textarea`:** Enter allein fügt eine neue Zeile ein und speichert nicht; Strg+Enter speichert. (Test in Task 3)
3. **Server-Fehler am Feld:** Ein 422 lässt das Feld offen, zeigt die Meldung und behält den eingegebenen Wert. (Tests in Task 3 und Task 1)
4. **Leeren optionaler Felder:** Wird z.B. die Seriennummer geleert, wird `null` gesendet, nicht `""`; die Anzeige zeigt danach „—“. (Test in Task 3)
5. **Eingeklappt, aber Aktion nötig:** „Neue Rechnung“ ist bedienbar, während „Rechnungen“ eingeklappt ist. (Test in Task 2)

---

### Task 1: Backend: Item-Update validieren

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/items.py` (`update_item`)
- Modify: `src/backend/mv_hofki/schemas/inventory_item.py` (`ItemUpdateBase`)
- Test: `tests/backend/test_items.py` (anhängen)

- [ ] **Step 1: Failing tests**

```python
# ---------------------------------------------------------------------------
# Partial updates used by inline editing
# ---------------------------------------------------------------------------


async def _general_item(client):
    resp = await client.post(
        "/api/v1/items", json={"category": "general_item", "label": "Stehtisch"}
    )
    return resp.json()["id"]


@pytest.mark.parametrize(
    "patch",
    [
        {"quantity": 0},
        {"quantity": None},
        {"owner": ""},
        {"owner": "   "},
        {"owner": None},
        {"label": ""},
        {"label": None},
    ],
)
async def test_invalid_partial_update_is_422_and_changes_nothing(client, patch):
    item_id = await _general_item(client)
    resp = await client.put(f"/api/v1/items/{item_id}", json=patch)
    assert resp.status_code == 422, resp.text
    detail = (await client.get(f"/api/v1/items/{item_id}")).json()
    assert detail["label"] == "Stehtisch"
    assert detail["owner"] == "MV Hofkirchen"
    assert detail["quantity"] == 1


async def test_required_field_message(client):
    item_id = await _general_item(client)
    resp = await client.put(f"/api/v1/items/{item_id}", json={"owner": ""})
    assert "Pflichtfeld" in resp.json()["detail"][0]["msg"]


async def test_single_field_updates_still_work(client):
    item_id = await _general_item(client)
    resp = await client.put(f"/api/v1/items/{item_id}", json={"notes": "wackelt"})
    assert resp.status_code == 200 and resp.json()["notes"] == "wackelt"
    resp = await client.put(f"/api/v1/items/{item_id}", json={"notes": None})
    assert resp.status_code == 200 and resp.json()["notes"] is None
    resp = await client.put(f"/api/v1/items/{item_id}", json={"quantity": 3})
    assert resp.json()["quantity"] == 3
```

Der Standard-Eigentümer ist laut `ItemCreateBase` „MV Hofkirchen“.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.** Erwartet sind 500 statt 422 bzw. 200 statt 422. Run: `IN_CONTAINER 'python -m pytest tests/backend/test_items.py -q -k "partial or required or single_field"'`.

- [ ] **Step 3: Schema.** In `ItemUpdateBase` ergänzen (Import `model_validator` ist schon da, `field_validator` bei Bedarf importieren):

```python
    @model_validator(mode="after")
    def required_fields_not_cleared(self):
        for name in ("label", "owner", "quantity"):
            if name in self.model_fields_set:
                value = getattr(self, name)
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise ValueError(f"Pflichtfeld: {name}")
        return self
```

Pydantic meldet das als `"Value error, Pflichtfeld: owner"`. Das Frontend entfernt „Value error, “ (`api.js`), übrig bleibt „Pflichtfeld: owner“. Das Feld-Label zeigt das Frontend selbst.

- [ ] **Step 4: Route.** In `update_item` die Zeile `validated = schema_cls(**body)` genauso in `try/except ValidationError` einbetten wie in `create_item` (derselbe 422-Block mit `loc`/`msg`/`type`). `ValidationError` und `HTTPException` werden dort lokal importiert, wie in `create_item`.

- [ ] **Step 5: Tests laufen lassen, sie müssen bestehen.** Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`. Commit: `fix(items): 422 instead of 500 for invalid updates, keep required fields`.

---

### Task 2: Einklappbare Abschnitte (Bausteine)

**Files:**
- Create: `src/frontend/src/composables/useSectionCollapse.js`
- Create: `src/frontend/src/components/CollapsibleSection.vue`
- Modify: `src/frontend/src/pages/ItemListPage.vue` (abgerundete Ecken der Gruppenüberschriften)
- Test: `tests/frontend/useSectionCollapse.test.js`, `tests/frontend/CollapsibleSection.test.js`

**Interfaces:**
- **`useSectionCollapse(scope: string, section: string) -> { open: Ref<boolean>, toggle() }`**
- **`<CollapsibleSection scope section title :summary>`**
  - Slots: Standard-Slot (Inhalt) und `actions` (rechts im Kopf, immer sichtbar).
  - Rendert `<section class="page-section">`.

- [ ] **Step 1: Failing tests**

`tests/frontend/useSectionCollapse.test.js`:

```js
import { describe, it, expect, beforeEach } from "vitest";
import { useSectionCollapse } from "../../src/frontend/src/composables/useSectionCollapse.js";

beforeEach(() => localStorage.clear());

describe("useSectionCollapse", () => {
  it("defaults to open, toggles and persists per scope and section", () => {
    const a = useSectionCollapse("instrument", "master");
    expect(a.open.value).toBe(true);
    a.toggle();
    expect(a.open.value).toBe(false);
    expect(localStorage.getItem("detail-collapsed:instrument:master")).toBe("1");
    expect(useSectionCollapse("instrument", "master").open.value).toBe(false);
    expect(useSectionCollapse("clothing", "master").open.value).toBe(true);
    a.toggle();
    expect(localStorage.getItem("detail-collapsed:instrument:master")).toBe(null);
  });

  it("works when storage throws", () => {
    const orig = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    try {
      const s = useSectionCollapse("x", "y");
      expect(s.open.value).toBe(true);
      s.toggle();
      expect(s.open.value).toBe(false);
    } finally {
      Storage.prototype.getItem = orig;
    }
  });
});
```

`tests/frontend/CollapsibleSection.test.js`:

```js
import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import CollapsibleSection from "../../src/frontend/src/components/CollapsibleSection.vue";

beforeEach(() => localStorage.clear());

function mountSection(extra = {}) {
  return mount(CollapsibleSection, {
    props: { scope: "instrument", section: "invoices", title: "Rechnungen", summary: "2 · 150,00 €", ...extra },
    slots: {
      default: "<p class='body'>Inhalt</p>",
      actions: "<button class='act'>Neue Rechnung</button>",
    },
  });
}

describe("CollapsibleSection", () => {
  it("is a heading with a disclosure button controlling the content", () => {
    const w = mountSection();
    const btn = w.find("h2 button");
    expect(btn.text()).toContain("Rechnungen");
    expect(btn.attributes("aria-expanded")).toBe("true");
    const panel = w.find(`#${btn.attributes("aria-controls")}`);
    expect(panel.exists()).toBe(true);
    expect(w.find(".body").isVisible()).toBe(true);
    expect(w.find(".section-summary").exists()).toBe(false);
  });

  it("collapses, shows the summary and keeps actions usable", async () => {
    const w = mountSection();
    await w.find("h2 button").trigger("click");
    expect(w.find("h2 button").attributes("aria-expanded")).toBe("false");
    expect(w.find(".body").exists()).toBe(false);
    expect(w.find(".section-summary").text()).toBe("2 · 150,00 €");
    expect(w.find(".act").exists()).toBe(true);
    expect(localStorage.getItem("detail-collapsed:instrument:invoices")).toBe("1");
  });

  it("restores the saved state", () => {
    localStorage.setItem("detail-collapsed:instrument:invoices", "1");
    const w = mountSection();
    expect(w.find("h2 button").attributes("aria-expanded")).toBe("false");
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.**

- [ ] **Step 3: `composables/useSectionCollapse.js`**

```js
/** Open/closed state of one detail-page section, shared by all pages of a kind. */
import { ref } from "vue";

const key = (scope, section) => `detail-collapsed:${scope}:${section}`;

export function useSectionCollapse(scope, section) {
  let collapsed = false;
  try {
    collapsed = localStorage.getItem(key(scope, section)) === "1";
  } catch {
    collapsed = false;
  }
  const open = ref(!collapsed);

  function toggle() {
    open.value = !open.value;
    try {
      if (open.value) localStorage.removeItem(key(scope, section));
      else localStorage.setItem(key(scope, section), "1");
    } catch {
      // storage unavailable: state lasts for this visit only
    }
  }

  return { open, toggle };
}
```

- [ ] **Step 4: `components/CollapsibleSection.vue`**

```vue
<script setup>
import { useSectionCollapse } from "../composables/useSectionCollapse.js";

const props = defineProps({
  scope: { type: String, required: true },
  section: { type: String, required: true },
  title: { type: String, required: true },
  summary: { type: String, default: "" },
});

const { open, toggle } = useSectionCollapse(props.scope, props.section);
const panelId = `section-${props.scope}-${props.section}`;
</script>

<template>
  <section class="page-section collapsible-section">
    <div class="section-header">
      <h2 class="collapsible-heading">
        <button
          type="button"
          class="collapsible-toggle"
          :aria-expanded="String(open)"
          :aria-controls="panelId"
          @click="toggle"
        >
          <span class="collapsible-chevron" aria-hidden="true">{{ open ? "▾" : "▸" }}</span>
          <span>{{ title }}</span>
          <span v-if="!open && summary" class="section-summary">{{ summary }}</span>
        </button>
      </h2>
      <div v-if="$slots.actions" class="collapsible-actions">
        <slot name="actions" />
      </div>
    </div>
    <div v-if="open" :id="panelId" class="collapsible-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.collapsible-heading {
  margin: 0;
  font-size: inherit;
}

.collapsible-toggle {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.collapsible-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.collapsible-chevron {
  width: 1em;
  color: var(--color-muted);
}

.section-summary {
  font-weight: 400;
  font-size: 0.875rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.collapsible-actions {
  display: flex;
  gap: var(--space-2);
}
</style>
```

Vorher `.section-header h2` in `style.css` ansehen: Die Schriftgröße der `h2` kommt von dort. `.collapsible-heading` darf sie nicht zurücksetzen. Ist `font-size: inherit` falsch, weil die globale Regel die `h2` stylt, den Button-Font per `font: inherit` von der `h2` erben lassen und `.collapsible-heading` keine eigene Größe geben. Das Erscheinungsbild der Überschriften muss gleich bleiben.

Ist `aria-controls` gesetzt, während der Inhalt eingeklappt aus dem DOM ist, verweist er auf ein fehlendes Element. Das ist nach ARIA Authoring Practices zulässig, wird aber besser vermieden: `:aria-controls="open ? panelId : undefined"`. Der erste Test prüft die Verknüpfung im offenen Zustand.

- [ ] **Step 5: Abgerundete Ecken der Gruppenüberschriften** in `ItemListPage.vue`. Die Klasse `item-grid-group` sitzt jetzt auf einem Wrapper, der `border-radius` wirkt deshalb nicht mehr auf den sichtbaren Button. Die Regel im scoped-Block ergänzen: `.item-grid-group :deep(.group-header) { border-radius: var(--radius-sm); }`. Einen Radius auf dem Wrapper selbst entfernen.

- [ ] **Step 6: Tests, Build, Commit.** Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`. Commit: `feat(frontend): collapsible detail sections with remembered state`.

---

### Task 3: Bearbeiten Feld für Feld (Bausteine)

**Files:**
- Create: `src/frontend/src/composables/useInlineEdit.js`
- Create: `src/frontend/src/components/InlineField.vue`
- Create: `src/frontend/src/lib/format.js` (`formatDate`, `formatMoney`)
- Test: `tests/frontend/useInlineEdit.test.js`, `tests/frontend/InlineField.test.js`, `tests/frontend/format.test.js`

**Interfaces:**
- **`useInlineEdit(save: (patch) => Promise<any>)`:** liefert `{ editingKey, savingKey, savedKey, error, start(key), cancel(), commit(key, patch) }`.
- **`formatDate(iso) -> "TT.MM.JJJJ" | "—"`**
- **`formatMoney(amount, abbreviation) -> "1.250,00 €" | "—"`**
- **`<InlineField>`:**
  - Props: `fieldKey`, `label`, `type` (`text|textarea|number|date|select|bool|multiselect|tags|money`), `value`, `options` (`[{value,label}]`), `required`, `min`, `max`, `placeholder`, `createOption` (für `tags`), `currencies` (für `money`: `[{id, abbreviation}]`), `editing`, `saving`, `saved`, `error`.
  - Emits: `start`, `cancel`, `save(value)`.
  - Slot: `display` (`{ value }`).
  - **Wertformen:**
    - `money`: `{ amount: number|null, currency_id: number|null }`
    - `multiselect` und `tags`: `number[]`
    - `select`: id oder String, wie `options[].value`
    - `bool`: `true|false`
    - `number`: `number|null`

- [ ] **Step 1: Failing tests**

`tests/frontend/format.test.js`:

```js
import { describe, it, expect } from "vitest";
import { formatDate, formatMoney } from "../../src/frontend/src/lib/format.js";

describe("format", () => {
  it("dates", () => {
    expect(formatDate("2026-03-01")).toBe("01.03.2026");
    expect(formatDate(null)).toBe("—");
    expect(formatDate("")).toBe("—");
  });
  it("money", () => {
    expect(formatMoney(1250, "€")).toBe("1.250,00 €");
    expect(formatMoney(0.5, "CHF")).toBe("0,50 CHF");
    expect(formatMoney(null, "€")).toBe("—");
  });
});
```

`tests/frontend/useInlineEdit.test.js`:

```js
import { describe, it, expect, vi, afterEach } from "vitest";
import { useInlineEdit } from "../../src/frontend/src/composables/useInlineEdit.js";

afterEach(() => vi.useRealTimers());

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
```

`tests/frontend/InlineField.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import InlineField from "../../src/frontend/src/components/InlineField.vue";

function mountField(props) {
  return mount(InlineField, {
    props: { fieldKey: "f", label: "Seriennummer", type: "text", value: "S-1", ...props },
    attachTo: document.body,
  });
}

describe("InlineField display", () => {
  it("shows dt/dd, value and a named edit button", async () => {
    const w = mountField({});
    expect(w.find("dt").text()).toBe("Seriennummer");
    expect(w.find("dd").text()).toContain("S-1");
    const btn = w.find('button[aria-label="„Seriennummer“ bearbeiten"]');
    await btn.trigger("click");
    expect(w.emitted("start")).toHaveLength(1);
  });

  it("formats empty, bool, select, multiselect, date and money", () => {
    expect(mountField({ value: null }).find("dd").text()).toContain("—");
    expect(mountField({ type: "bool", value: true }).find("dd").text()).toContain("Ja");
    const opts = [{ value: 1, label: "Tuba" }, { value: 2, label: "Horn" }];
    expect(mountField({ type: "select", value: 2, options: opts }).find("dd").text()).toContain("Horn");
    expect(mountField({ type: "multiselect", value: [1, 2], options: opts }).find("dd").text()).toContain("Tuba, Horn");
    expect(mountField({ type: "date", value: "2026-03-01" }).find("dd").text()).toContain("01.03.2026");
    const money = mountField({
      type: "money",
      value: { amount: 1250, currency_id: 3 },
      currencies: [{ id: 3, abbreviation: "€" }],
    });
    expect(money.find("dd").text()).toContain("1.250,00 €");
  });

  it("shows saving and saved states", () => {
    expect(mountField({ saving: true }).text()).toContain("Speichert …");
    expect(mountField({ saved: true }).find('[role="status"]').text()).toBe("Gespeichert");
  });
});

describe("InlineField editing", () => {
  it("text: focuses, saves on Enter, cancels on Escape", async () => {
    const w = mountField({ editing: true });
    const input = w.find("input");
    expect(document.activeElement).toBe(input.element);
    await input.setValue("S-2");
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("save")).toEqual([["S-2"]]);
    await input.trigger("keydown", { key: "Escape" });
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("empty optional text saves null; required shows Pflichtfeld", async () => {
    const w = mountField({ editing: true });
    await w.find("input").setValue("  ");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[null]]);
    const r = mountField({ editing: true, required: true });
    await r.find("input").setValue("");
    await r.find(".inline-save").trigger("click");
    expect(r.emitted("save")).toBeUndefined();
    expect(r.find('[role="alert"]').text()).toBe("Pflichtfeld");
  });

  it("textarea: Enter adds a line, Ctrl+Enter saves", async () => {
    const w = mountField({ type: "textarea", value: "a", editing: true });
    const ta = w.find("textarea");
    await ta.setValue("a\nb");
    await ta.trigger("keydown", { key: "Enter" });
    expect(w.emitted("save")).toBeUndefined();
    await ta.trigger("keydown", { key: "Enter", ctrlKey: true });
    expect(w.emitted("save")).toEqual([["a\nb"]]);
  });

  it("number: integer checks with min/max", async () => {
    const w = mountField({ type: "number", value: 1, min: 1, max: 5, editing: true, required: true });
    const input = w.find("input");
    await input.setValue("0");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Mindestens 1");
    await input.setValue("6");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Höchstens 5");
    await input.setValue("2.5");
    await w.find(".inline-save").trigger("click");
    expect(w.find('[role="alert"]').text()).toBe("Bitte eine ganze Zahl eingeben.");
    await input.setValue("3");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[3]]);
  });

  it("select with empty option for optional fields", async () => {
    const opts = [{ value: 1, label: "Marsch" }];
    const w = mountField({ type: "select", value: 1, options: opts, editing: true });
    expect(w.findAll("option").map((o) => o.text())).toEqual(["—", "Marsch"]);
    await w.find("select").setValue("");
    await w.find(".inline-save").trigger("click");
    expect(w.emitted("save")).toEqual([[null]]);
  });

  it("bool, multiselect and money", async () => {
    const b = mountField({ type: "bool", value: false, editing: true });
    await b.find('input[type="checkbox"]').setValue(true);
    await b.find(".inline-save").trigger("click");
    expect(b.emitted("save")).toEqual([[true]]);

    const opts = [{ value: 1, label: "Tuba" }, { value: 2, label: "Horn" }];
    const m = mountField({ type: "multiselect", value: [1], options: opts, editing: true });
    await m.findAll('input[type="checkbox"]')[1].setValue(true);
    await m.find(".inline-save").trigger("click");
    expect(m.emitted("save")).toEqual([[[1, 2]]]);

    const cur = [{ id: 3, abbreviation: "€" }];
    const money = mountField({ type: "money", value: { amount: null, currency_id: null }, currencies: cur, editing: true });
    await money.find('input[type="number"]').setValue("12.5");
    await money.find(".inline-save").trigger("click");
    expect(money.find('[role="alert"]').text()).toBe("Bitte eine Währung wählen.");
    await money.find("select").setValue("3");
    await money.find(".inline-save").trigger("click");
    expect(money.emitted("save")).toEqual([[{ amount: 12.5, currency_id: 3 }]]);
  });

  it("shows a server error and keeps the typed value", async () => {
    const w = mountField({ editing: true, error: "Pflichtfeld: owner" });
    expect(w.find('[role="alert"]').text()).toBe("Pflichtfeld: owner");
    await w.find("input").setValue("neu");
    await w.setProps({ error: "anders" });
    expect(w.find("input").element.value).toBe("neu");
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.**

- [ ] **Step 3: `lib/format.js`**

```js
/** Display formatting shared by detail pages (de-AT). */
export function formatDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = String(iso).slice(0, 10).split("-");
  return d ? `${d}.${m}.${y}` : String(iso);
}

export function formatMoney(amount, abbreviation) {
  if (amount === null || amount === undefined || amount === "") return "—";
  const n = Number(amount).toLocaleString("de-AT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return abbreviation ? `${n} ${abbreviation}` : n;
}
```

Zu `formatMoney(1250)`: `de-AT` liefert in Node/ICU „1.250,00“. Zeigt jsdom oder Node ein schmales geschütztes Leerzeichen als Tausendertrenner, den Test auf den tatsächlichen `de-AT`-Wert von `Intl` umstellen: `expect(...).toBe(\`${(1250).toLocaleString("de-AT", {minimumFractionDigits: 2})} €\`)`. Die Begründung gehört in den Report.

- [ ] **Step 4: `composables/useInlineEdit.js`**

```js
/** One-field-at-a-time inline editing with save state for a detail page. */
import { ref } from "vue";

export function useInlineEdit(save) {
  const editingKey = ref(null);
  const savingKey = ref(null);
  const savedKey = ref(null);
  const error = ref("");
  let savedTimer = null;

  function start(key) {
    editingKey.value = key;
    error.value = "";
  }

  function cancel() {
    editingKey.value = null;
    error.value = "";
  }

  async function commit(key, patch) {
    savingKey.value = key;
    error.value = "";
    try {
      await save(patch);
      editingKey.value = null;
      savedKey.value = key;
      clearTimeout(savedTimer);
      savedTimer = setTimeout(() => {
        if (savedKey.value === key) savedKey.value = null;
      }, 2000);
    } catch (e) {
      error.value = e?.message || "Speichern fehlgeschlagen.";
    } finally {
      savingKey.value = null;
    }
  }

  return { editingKey, savingKey, savedKey, error, start, cancel, commit };
}
```

- [ ] **Step 5: `components/InlineField.vue`**

```vue
<script setup>
import { computed, nextTick, ref, watch } from "vue";
import TagSelect from "./TagSelect.vue";
import { formatDate, formatMoney } from "../lib/format.js";

const props = defineProps({
  fieldKey: { type: String, required: true },
  label: { type: String, required: true },
  type: { type: String, default: "text" },
  value: { type: [String, Number, Boolean, Array, Object], default: null },
  options: { type: Array, default: () => [] },
  required: Boolean,
  min: { type: Number, default: null },
  max: { type: Number, default: null },
  placeholder: { type: String, default: "" },
  createOption: { type: Function, default: null },
  currencies: { type: Array, default: () => [] },
  editing: Boolean,
  saving: Boolean,
  saved: Boolean,
  error: { type: String, default: "" },
});
const emit = defineEmits(["start", "cancel", "save"]);

const inputId = `inline-${props.fieldKey}-${Math.random().toString(36).slice(2, 7)}`;
const draft = ref(null);
const localError = ref("");
const editor = ref(null);
const editButton = ref(null);

const optionLabel = (v) => props.options.find((o) => String(o.value) === String(v))?.label;

const display = computed(() => {
  const v = props.value;
  switch (props.type) {
    case "bool":
      return v ? "Ja" : "Nein";
    case "select":
      return v === null || v === undefined || v === "" ? "—" : (optionLabel(v) ?? String(v));
    case "multiselect":
      return v?.length ? v.map((x) => optionLabel(x) ?? x).join(", ") : "—";
    case "date":
      return formatDate(v);
    case "money": {
      const abbr = props.currencies.find((c) => c.id === v?.currency_id)?.abbreviation;
      return formatMoney(v?.amount, abbr);
    }
    default:
      return v === null || v === undefined || v === "" ? "—" : String(v);
  }
});

function initialDraft() {
  const v = props.value;
  if (props.type === "money") return { amount: v?.amount ?? "", currency_id: v?.currency_id ?? "" };
  if (props.type === "multiselect" || props.type === "tags") return [...(v || [])];
  if (props.type === "bool") return !!v;
  return v ?? "";
}

watch(
  () => props.editing,
  async (editing) => {
    localError.value = "";
    if (editing) {
      draft.value = initialDraft();
      await nextTick();
      editor.value?.querySelector("input, select, textarea")?.focus();
    } else {
      await nextTick();
      editButton.value?.focus?.();
    }
  },
  { immediate: true },
);

function parsed() {
  const d = draft.value;
  switch (props.type) {
    case "number": {
      if (d === "" || d === null) return props.required ? { error: "Pflichtfeld" } : { value: null };
      const n = Number(d);
      if (!Number.isInteger(n)) return { error: "Bitte eine ganze Zahl eingeben." };
      if (props.min !== null && n < props.min) return { error: `Mindestens ${props.min}` };
      if (props.max !== null && n > props.max) return { error: `Höchstens ${props.max}` };
      return { value: n };
    }
    case "select":
      if (d === "" || d === null) return props.required ? { error: "Pflichtfeld" } : { value: null };
      return { value: props.options.find((o) => String(o.value) === String(d))?.value ?? d };
    case "bool":
      return { value: !!d };
    case "multiselect":
    case "tags":
      return { value: [...d] };
    case "money": {
      const amount = d.amount === "" || d.amount === null ? null : Number(d.amount);
      const currency = d.currency_id === "" || d.currency_id === null ? null : Number(d.currency_id);
      if (amount !== null && Number.isNaN(amount)) return { error: "Bitte einen Betrag eingeben." };
      if (amount !== null && currency === null) return { error: "Bitte eine Währung wählen." };
      return { value: { amount, currency_id: currency } };
    }
    default: {
      const s = typeof d === "string" ? d.trim() : d;
      if (!s) return props.required ? { error: "Pflichtfeld" } : { value: null };
      return { value: props.type === "textarea" ? d : s };
    }
  }
}

function submit() {
  const result = parsed();
  if (result.error) {
    localError.value = result.error;
    return;
  }
  localError.value = "";
  emit("save", result.value);
}

function onKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    emit("cancel");
  } else if (e.key === "Enter") {
    if (props.type === "textarea" && !(e.ctrlKey || e.metaKey)) return;
    if (props.type === "tags" || props.type === "multiselect") return;
    e.preventDefault();
    submit();
  }
}

function toggleMulti(value, checked) {
  draft.value = checked ? [...draft.value, value] : draft.value.filter((x) => x !== value);
}

const shownError = computed(() => localError.value || props.error);
</script>

<template>
  <dt>
    <label v-if="editing && !['multiselect', 'bool', 'tags'].includes(type)" :for="inputId">{{ label }}</label>
    <template v-else>{{ label }}</template>
  </dt>
  <dd class="inline-field" :class="{ 'is-editing': editing }">
    <template v-if="!editing">
      <span class="inline-value">
        <slot name="display" :value="value">{{ display }}</slot>
      </span>
      <button
        ref="editButton"
        type="button"
        class="inline-edit-btn"
        :aria-label="`„${label}“ bearbeiten`"
        :disabled="saving"
        @click="emit('start')"
      >
        <span aria-hidden="true">✎</span>
      </button>
      <span v-if="saving" class="inline-status">Speichert …</span>
      <span v-else-if="saved" class="inline-status inline-saved" role="status">Gespeichert</span>
    </template>

    <div v-else ref="editor" class="inline-editor" @keydown="onKeydown">
      <textarea v-if="type === 'textarea'" :id="inputId" v-model="draft" rows="3" :placeholder="placeholder" />
      <input v-else-if="type === 'number'" :id="inputId" v-model="draft" type="number" inputmode="numeric" :min="min ?? undefined" :max="max ?? undefined" step="1" class="input-narrow" />
      <input v-else-if="type === 'date'" :id="inputId" v-model="draft" type="date" class="input-narrow" />
      <select v-else-if="type === 'select'" :id="inputId" v-model="draft">
        <option v-if="!required" value="">—</option>
        <option v-for="o in options" :key="String(o.value)" :value="o.value">{{ o.label }}</option>
      </select>
      <label v-else-if="type === 'bool'" class="inline-check">
        <input v-model="draft" type="checkbox" />
        {{ label }}
      </label>
      <fieldset v-else-if="type === 'multiselect'" class="inline-multi">
        <legend class="sr-only">{{ label }}</legend>
        <label v-for="o in options" :key="String(o.value)" class="inline-check">
          <input type="checkbox" :checked="draft.includes(o.value)" @change="toggleMulti(o.value, $event.target.checked)" />
          {{ o.label }}
        </label>
      </fieldset>
      <TagSelect v-else-if="type === 'tags'" v-model="draft" :options="options.map((o) => ({ id: o.value, label: o.label }))" :label="label" :create-option="createOption" />
      <div v-else-if="type === 'money'" class="inline-money">
        <input :id="inputId" v-model="draft.amount" type="number" step="0.01" min="0" class="input-narrow" :aria-label="`${label}: Betrag`" />
        <select v-model="draft.currency_id" :aria-label="`${label}: Währung`">
          <option value="">—</option>
          <option v-for="c in currencies" :key="c.id" :value="c.id">{{ c.abbreviation }}</option>
        </select>
      </div>
      <input v-else :id="inputId" v-model="draft" type="text" :placeholder="placeholder" />

      <div class="inline-actions">
        <button type="button" class="btn-sm btn-primary inline-save" :disabled="saving" @click="submit">
          {{ saving ? "Speichert …" : "Speichern" }}
        </button>
        <button type="button" class="btn-sm inline-cancel" :disabled="saving" @click="emit('cancel')">Abbrechen</button>
      </div>
      <p v-if="shownError" class="form-error" role="alert">{{ shownError }}</p>
    </div>
  </dd>
</template>

<style scoped>
.inline-field {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.inline-value {
  flex: 1 1 auto;
  min-width: 0;
}

.inline-edit-btn {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.inline-edit-btn:hover,
.inline-edit-btn:focus-visible {
  border-color: var(--color-border);
  color: var(--color-primary);
}

.inline-status {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.inline-saved {
  color: var(--color-success);
}

.inline-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
}

.inline-actions {
  display: flex;
  gap: var(--space-2);
}

.inline-actions .btn-sm {
  min-height: 44px;
}

.inline-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.inline-check input {
  width: auto;
}

.inline-multi {
  margin: 0;
  padding: 0;
  border: none;
}

.inline-money {
  display: flex;
  gap: var(--space-2);
}

.inline-money select {
  width: auto;
}
</style>
```

Hinweise:
- `--color-success` gibt es in `style.css` (Badges verwenden es); das vorher prüfen.
- Scheitert der Focus-Test, weil das Element erst nach dem `nextTick` im Watcher existiert, im Test `await nextTick()` bzw. `flushPromises()` ergänzen und das im Report begründen.
- Zum Test „shows a server error …“: Der Entwurf bleibt erhalten, weil `draft` nur beim Wechsel von `editing` zurückgesetzt wird.

- [ ] **Step 6: Tests, Build, Commit.** Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`. Commit: `feat(frontend): inline field editing building blocks`.

---

### Task 4: Item-Detailseite

**Files:**
- Create: `src/frontend/src/lib/itemFields.js`
- Modify: `src/frontend/src/pages/ItemDetailPage.vue`
- Test: `tests/frontend/itemFields.test.js`

**Interfaces:**
- `itemFieldDefs(category, ctx) -> FieldDef[]`
  - `ctx = { types, genres, categories, currencies }` (Arrays aus der API; `types` = Instrumenten- bzw. Kleidungstypen mit `id`, `label`, für Instrumente auch `label_short`).
  - `FieldDef = { key, label, type, required?, min?, max?, options?, value(item), toPatch(value, item) }`.
- `renumberPrefix(item, newTypeId, types) -> string | null`: das neue Kürzel, wenn es sich vom aktuellen `number_prefix` unterscheidet (nur bei Instrumenten), sonst `null`.

- [ ] **Step 1: Failing test** `tests/frontend/itemFields.test.js`:

```js
import { describe, it, expect } from "vitest";
import { itemFieldDefs, renumberPrefix } from "../../src/frontend/src/lib/itemFields.js";

const ctx = {
  types: [
    { id: 1, label: "Tuba", label_short: "TU" },
    { id: 2, label: "Horn", label_short: "HR" },
    { id: 3, label: "Basstuba", label_short: "TU" },
  ],
  genres: [{ id: 7, label: "Marsch" }],
  categories: [{ id: 9, label: "Deko" }],
  currencies: [{ id: 4, abbreviation: "€" }],
};
const keys = (cat) => itemFieldDefs(cat, ctx).map((f) => f.key);

describe("itemFieldDefs", () => {
  it("lists the fields per kind", () => {
    expect(keys("instrument")).toEqual([
      "type", "quantity", "serial_nr", "manufacturer", "construction_year", "distributor",
      "container", "particularities", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("clothing")).toEqual([
      "type", "quantity", "size", "gender", "manufacturer", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("sheet_music")).toEqual([
      "label", "quantity", "composer", "arranger", "difficulty", "genre", "storage_location",
      "manufacturer", "owner", "acquisition_date", "acquisition_cost", "notes",
    ]);
    expect(keys("general_item")).toEqual([
      "label", "quantity", "categories", "storage_location", "manufacturer", "owner",
      "acquisition_date", "acquisition_cost", "notes",
    ]);
  });

  it("type changes also set the label", () => {
    const type = itemFieldDefs("instrument", ctx).find((f) => f.key === "type");
    expect(type.required).toBe(true);
    expect(type.value({ instrument_type_id: 1 })).toBe(1);
    expect(type.toPatch(2)).toEqual({ instrument_type_id: 2, label: "Horn" });
    const clothing = itemFieldDefs("clothing", { ...ctx, types: [{ id: 5, label: "Hut" }] }).find((f) => f.key === "type");
    expect(clothing.toPatch(5)).toEqual({ clothing_type_id: 5, label: "Hut" });
  });

  it("money, categories and genre map to the API fields", () => {
    const defs = Object.fromEntries(itemFieldDefs("general_item", ctx).map((f) => [f.key, f]));
    expect(defs.acquisition_cost.value({ acquisition_cost: 12, currency_id: 4 })).toEqual({ amount: 12, currency_id: 4 });
    expect(defs.acquisition_cost.toPatch({ amount: null, currency_id: null })).toEqual({ acquisition_cost: null, currency_id: null });
    expect(defs.categories.value({ categories: [{ id: 9, label: "Deko" }] })).toEqual([9]);
    expect(defs.categories.toPatch([9])).toEqual({ category_ids: [9] });
    const genre = itemFieldDefs("sheet_music", ctx).find((f) => f.key === "genre");
    expect(genre.toPatch(null)).toEqual({ genre_id: null });
    const year = itemFieldDefs("instrument", ctx).find((f) => f.key === "construction_year");
    expect(year.min).toBe(1800);
    expect(year.max).toBe(new Date().getFullYear() + 1);
  });

  it("detects renumbering only when the short code changes", () => {
    const item = { category: "instrument", number_prefix: "TU" };
    expect(renumberPrefix(item, 2, ctx.types)).toBe("HR");
    expect(renumberPrefix(item, 3, ctx.types)).toBe(null);
    expect(renumberPrefix({ category: "clothing", number_prefix: "K" }, 2, ctx.types)).toBe(null);
  });
});
```

Die Item-Antwort enthält `number_prefix` womöglich nicht. `_build_read_dict` liefert `display_nr` und `inventory_nr`. `renumberPrefix` liest das Kürzel deshalb aus `item.number_prefix ?? item.display_nr.split("-")[0]`, und der Test deckt beides ab (zusätzlich `renumberPrefix({ category: "instrument", display_nr: "TU-002" }, 2, ctx.types)` ergibt `"HR"`).

- [ ] **Step 2: Test laufen lassen, er muss scheitern.**

- [ ] **Step 3: `lib/itemFields.js`**

```js
/** Inline-editable master-data fields of an item, per kind. */

const opt = (rows) => rows.map((r) => ({ value: r.id, label: r.label }));
const same = (key) => ({ value: (item) => item[key] ?? null, toPatch: (v) => ({ [key]: v }) });

const COMMON_TAIL = [
  { key: "manufacturer", label: "Hersteller", type: "text", ...same("manufacturer") },
  { key: "owner", label: "Eigentümer", type: "text", required: true, ...same("owner") },
  { key: "acquisition_date", label: "Anschaffungsdatum", type: "date", ...same("acquisition_date") },
  {
    key: "acquisition_cost",
    label: "Anschaffungskosten",
    type: "money",
    value: (item) => ({ amount: item.acquisition_cost ?? null, currency_id: item.currency_id ?? null }),
    toPatch: (v) => ({ acquisition_cost: v.amount, currency_id: v.currency_id }),
  },
  { key: "notes", label: "Notizen", type: "textarea", ...same("notes") },
];

const QUANTITY = { key: "quantity", label: "Menge", type: "number", required: true, min: 1, ...same("quantity") };

function typeField(idField, types) {
  return {
    key: "type",
    label: "Typ",
    type: "select",
    required: true,
    options: opt(types),
    value: (item) => item[idField] ?? null,
    toPatch: (v) => ({ [idField]: v, label: types.find((t) => t.id === v)?.label }),
  };
}

export function itemFieldDefs(category, { types = [], genres = [], categories = [] } = {}) {
  const withoutManufacturer = COMMON_TAIL.filter((f) => f.key !== "manufacturer");
  switch (category) {
    case "instrument":
      return [
        typeField("instrument_type_id", types),
        QUANTITY,
        { key: "serial_nr", label: "Seriennummer", type: "text", ...same("serial_nr") },
        { key: "manufacturer", label: "Hersteller", type: "text", ...same("manufacturer") },
        {
          key: "construction_year",
          label: "Baujahr",
          type: "number",
          min: 1800,
          max: new Date().getFullYear() + 1,
          ...same("construction_year"),
        },
        { key: "distributor", label: "Händler", type: "text", ...same("distributor") },
        { key: "container", label: "Behältnis", type: "text", ...same("container") },
        { key: "particularities", label: "Besonderheiten", type: "textarea", ...same("particularities") },
        ...withoutManufacturer,
      ];
    case "clothing":
      return [
        typeField("clothing_type_id", types),
        QUANTITY,
        { key: "size", label: "Größe", type: "text", ...same("size") },
        { key: "gender", label: "Geschlecht", type: "text", ...same("gender") },
        ...COMMON_TAIL,
      ];
    case "sheet_music":
      return [
        { key: "label", label: "Titel", type: "text", required: true, ...same("label") },
        QUANTITY,
        { key: "composer", label: "Komponist", type: "text", ...same("composer") },
        { key: "arranger", label: "Arrangeur", type: "text", ...same("arranger") },
        { key: "difficulty", label: "Schwierigkeitsgrad", type: "text", ...same("difficulty") },
        {
          key: "genre",
          label: "Gattung",
          type: "select",
          options: opt(genres),
          value: (item) => item.genre_id ?? null,
          toPatch: (v) => ({ genre_id: v }),
        },
        { key: "storage_location", label: "Lagerort", type: "text", ...same("storage_location") },
        ...COMMON_TAIL,
      ];
    default:
      return [
        { key: "label", label: "Bezeichnung", type: "text", required: true, ...same("label") },
        QUANTITY,
        {
          key: "categories",
          label: "Kategorien",
          type: "tags",
          options: opt(categories),
          value: (item) => (item.categories || []).map((c) => c.id),
          toPatch: (v) => ({ category_ids: v }),
        },
        { key: "storage_location", label: "Lagerort", type: "text", ...same("storage_location") },
        ...COMMON_TAIL,
      ];
  }
}

export function renumberPrefix(item, newTypeId, types) {
  if (item.category !== "instrument") return null;
  const current = item.number_prefix ?? String(item.display_nr || "").split("-")[0];
  const next = types.find((t) => t.id === newTypeId)?.label_short?.trim().toUpperCase();
  return next && next !== current ? next : null;
}
```

- [ ] **Step 4: ItemDetailPage umbauen**

**Script:**
- Imports: `CollapsibleSection`, `InlineField`, `useInlineEdit`, `itemFieldDefs`, `renumberPrefix`, `formatDate`, `formatMoney`, `CategoryChips` (vorhanden) und `quantityDetail` (vorhanden).
- Optionen laden: In `onMounted` zusätzlich, je nach Art, `/instrument-types`, `/clothing-types`, `/sheet-music-genres` bzw. `/general-item-categories` in die Refs `types`, `genres`, `categories` holen, jeweils mit `.catch(() => [])`.
- Felder: `const fields = computed(() => itemFieldDefs(props.category, { types: types.value, genres: genres.value, categories: categories.value, currencies: currencies.value }));`
- Bearbeiten:
  ```js
  const inline = useInlineEdit(async (patch) => {
    item.value = await put(`/items/${props.id}`, patch);
  });
  const pendingRenumber = ref(null); // { key, patch, from, to }

  function saveField(field, value) {
    const patch = field.toPatch(value, item.value);
    if (field.key === "type") {
      const next = renumberPrefix(item.value, value, types.value);
      if (next) {
        pendingRenumber.value = { key: field.key, patch, from: item.value.display_nr, to: `${next}-…` };
        return;
      }
    }
    inline.commit(field.key, patch);
  }

  function confirmRenumber() {
    const p = pendingRenumber.value;
    pendingRenumber.value = null;
    inline.commit(p.key, p.patch);
  }

  async function createCategory(label) {
    const created = await post("/general-item-categories", { label });
    categories.value = [...categories.value, created];
    return created;
  }
  ```
- Kurzinfos:
  ```js
  const photoSummary = computed(() => {
    const n = imageGroups.value.photos.length;
    return n ? `${n} ${n === 1 ? "Foto" : "Fotos"}` : "Keine Fotos";
  });
  const scanSummary = computed(() => {
    const n = imageGroups.value.scans.length;
    return `${n} ${n === 1 ? "Seite" : "Seiten"}`;
  });
  const masterSummary = computed(() =>
    [item.value?.display_nr, item.value?.manufacturer].filter(Boolean).join(" · "),
  );
  const loanSummary = computed(() =>
    activeLoan.value
      ? `an ${activeLoan.value.musician.first_name} ${activeLoan.value.musician.last_name} seit ${formatDate(activeLoan.value.start_date)}`
      : "verfügbar",
  );
  const invoiceSummary = computed(() => {
    if (!invoices.value.length) return "keine";
    const sums = {};
    for (const inv of invoices.value) {
      const abbr = inv.currency?.abbreviation || "";
      sums[abbr] = (sums[abbr] || 0) + Number(inv.amount || 0);
    }
    const totals = Object.entries(sums).map(([abbr, sum]) => formatMoney(sum, abbr)).join(" · ");
    return `${invoices.value.length} · ${totals}`;
  });
  const historySummary = computed(() => `${loans.value.length} ${loans.value.length === 1 ? "Eintrag" : "Einträge"}`);
  ```

**Template:**
- Jede `<section class="page-section">` wird eine `CollapsibleSection` mit `:scope="category"`:
  - `section="photos" title="Fotos" :summary="photoSummary"`. Der bisherige Sonderfall mit der unsichtbaren `h2` entfällt.
  - `v-if="imageGroups.scans.length" section="scans" title="Unterlagen (Scans)" :summary="scanSummary"`. Die Seitenzahl im Kopf entfällt, denn sie steht jetzt in der Kurzinfo.
  - `section="master" title="Stammdaten" :summary="masterSummary"`.
  - `v-if="cat.hasLoans" section="loan" title="Ausleihe" :summary="loanSummary"`.
  - `v-if="cat.hasInvoices" section="invoices" title="Rechnungen" :summary="invoiceSummary"` mit `<template #actions><button class="btn-sm" @click="newInvoice">Neue Rechnung</button></template>`.
  - `v-if="cat.hasLoans && loans.length" section="history" title="Leihhistorie" :summary="historySummary"`.
- **Stammdaten:**
  ```vue
  <dl class="detail-grid">
    <dt>Inventarnummer</dt>
    <dd>{{ item.display_nr }}</dd>
    <InlineField
      v-for="f in fields"
      :key="f.key"
      :field-key="f.key"
      :label="f.label"
      :type="f.type"
      :value="f.value(item)"
      :options="f.options || []"
      :required="!!f.required"
      :min="f.min ?? null"
      :max="f.max ?? null"
      :currencies="currencies"
      :create-option="f.type === 'tags' ? createCategory : null"
      :editing="inline.editingKey.value === f.key"
      :saving="inline.savingKey.value === f.key"
      :saved="inline.savedKey.value === f.key"
      :error="inline.editingKey.value === f.key ? inline.error.value : ''"
      @start="inline.start(f.key)"
      @cancel="inline.cancel()"
      @save="(v) => saveField(f, v)"
    >
      <template v-if="f.key === 'quantity'" #display>{{ quantityDetail(item) }}</template>
      <template v-else-if="f.key === 'categories'" #display>
        <CategoryChips :categories="item.categories || []" />
      </template>
    </InlineField>
  </dl>
  ```
  Die Refs im Objekt `inline` werden im Template nicht automatisch ausgepackt. Deshalb wird `.value` verwendet wie oben, oder `inline` wird destrukturiert (`const { editingKey, … } = useInlineEdit(…)`); beides ist in Ordnung.
- Bestätigung, direkt vor `ConfirmDialog` für Löschen:
  ```vue
  <ConfirmDialog
    :open="!!pendingRenumber"
    title="Neue Inventarnummer"
    :message="pendingRenumber ? `Die Inventarnummer wird neu vergeben: ${pendingRenumber.from} → ${pendingRenumber.to}` : ''"
    confirm-label="Typ ändern"
    @confirm="confirmRenumber"
    @cancel="pendingRenumber = null"
  />
  ```
  Prüfe, ob `ConfirmDialog` die Prop `confirmLabel` hat. Laut Code (`{{ confirmLabel }}`) ja. Bei „Abbrechen“ bleibt das Typ-Feld im Bearbeitungsmodus, weil `inline.cancel()` nicht aufgerufen wird.
- Die alte Stammdaten-`<dl>` wird vollständig ersetzt. Dabei entfallen der doppelte „Hersteller“ und die fehlende „Typ“-Zeile bei Instrumenten.
- Nach „Bearbeiten“ (Modal) bleibt `onEditSave` → `reload()` wie bisher.

Test zur Review Focus 1: In `tests/frontend/itemFields.test.js` wird die Logik geprüft. Den Dialogablauf zusätzlich über einen schlanken Komponententest `tests/frontend/ItemDetailRenumber.test.js` prüfen:
- ItemDetailPage mit gemocktem `lib/api.js` mounten: `get` liefert je nach Pfad Item, Typen, Bilder, Leihen und Rechnungen; `getAll` liefert `[]`.
- Den Typ ändern und „Speichern“ klicken. Erwartet: Es wurde kein `put` aufgerufen, und der Dialog ist offen.
- Im Dialog „Abbrechen“: Das Feld ist weiter im Bearbeitungsmodus, und `put` wurde nie aufgerufen.
- Beim zweiten Versuch „Typ ändern“: `put` wurde mit `{ instrument_type_id: 2, label: "Horn" }` aufgerufen.
- Für `HTMLDialogElement` gibt es das jsdom-Polyfill wie in `ScanDocuments.test.js`, falls `ConfirmDialog` ein `<dialog>` ist. Es ist ein `div.overlay`, dann ist nichts nötig.

- [ ] **Step 5: Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`.

Browser (echte DB, nur die erlaubte Schreibaktion aus den Global Constraints):
1. Ein Instrument öffnen: Alle Abschnitte sind einklappbar. „Stammdaten“ einklappen, dann ein anderes Instrument öffnen: Die Stammdaten sind auch dort eingeklappt, und die Kurzinfo stimmt. „Rechnungen“ einklappen: „Neue Rechnung“ bleibt bedienbar (nur öffnen, nicht speichern).
2. Bei Instrument A: „Notizen“ bearbeiten. Den Ursprungswert notieren, „Test“ ergänzen, Strg+Enter; „Gespeichert“ erscheint. Dann den Ursprungswert wiederherstellen und per `GET /api/v1/items/<id>` vergleichen.
3. „Eigentümer“ leeren und speichern: „Pflichtfeld“ erscheint am Feld, es wird nichts gesendet.
4. Den Typ-Dialog nur öffnen: einen Typ mit anderem Kürzel wählen, „Speichern“, der Dialog erscheint, dann **Abbrechen**, danach „Abbrechen“ am Feld.
5. Handy bei 390 px und dunkles Theme: Stift-Buttons, Eingabefelder und „Speichern“ sind bedienbar.

- [ ] **Step 6: Commit.** Message: `feat(items): collapsible detail sections and inline master data editing`.

---

### Task 5: Musiker-Detailseite

**Files:**
- Modify: `src/frontend/src/pages/MusicianDetailPage.vue`
- Create: `src/frontend/src/lib/musicianFields.js`
- Test: `tests/frontend/musicianFields.test.js`

**Interfaces:**
- `musicianFieldDefs(registers) -> { membership: FieldDef[], contact: FieldDef[] }` im selben `FieldDef`-Format wie in Task 4.

- [ ] **Step 1: Failing test**

```js
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
    expect(d.membership.find((f) => f.key === "is_active").label).toBe("Aktiv");
  });
});
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern.**

- [ ] **Step 3: `lib/musicianFields.js`**

```js
/** Inline-editable fields of a musician. */
const same = (key) => ({ value: (m) => m[key] ?? null, toPatch: (v) => ({ [key]: v }) });

export function musicianFieldDefs(registers = []) {
  return {
    membership: [
      { key: "is_active", label: "Aktiv", type: "bool", value: (m) => m.is_active !== false, toPatch: (v) => ({ is_active: v }) },
      {
        key: "registers",
        label: "Register",
        type: "multiselect",
        options: registers.map((r) => ({ value: r.id, label: r.label })),
        value: (m) => (m.registers || []).map((r) => r.id),
        toPatch: (v) => ({ register_ids: v }),
      },
      { key: "is_extern", label: "Extern", type: "bool", value: (m) => !!m.is_extern, toPatch: (v) => ({ is_extern: v }) },
      { key: "notes", label: "Notizen", type: "textarea", ...same("notes") },
    ],
    contact: [
      { key: "first_name", label: "Vorname", type: "text", required: true, ...same("first_name") },
      { key: "last_name", label: "Nachname", type: "text", required: true, ...same("last_name") },
      { key: "phone", label: "Telefon", type: "text", ...same("phone") },
      { key: "email", label: "E-Mail", type: "text", ...same("email") },
      { key: "street_address", label: "Adresse", type: "text", ...same("street_address") },
      { key: "postal_code", label: "PLZ", type: "number", min: 1000, max: 99999, ...same("postal_code") },
      { key: "city", label: "Ort", type: "text", ...same("city") },
    ],
  };
}
```

- [ ] **Step 4: MusicianDetailPage umbauen**

**Script:**
- `registers` laden: `sortRegisters(await get("/registers"))`, mit `.catch(() => [])`. Das geht in die bestehende `Promise.all`.
- `const defs = computed(() => musicianFieldDefs(registers.value));`
- `const inline = useInlineEdit(async (patch) => { musician.value = await put(\`/musicians/${route.params.id}\`, patch); });` (Import `put`).
- Kurzinfos:
  - `membershipSummary` = `${musician.is_active === false ? "Inaktiv" : "Aktiv"}`, dazu `" · " + registerLabels(musician)`, wenn Register vorhanden sind.
  - `contactSummary` = `musician.phone || musician.email || "—"`.
  - `historySummary` = „n Einträge“ bzw. „1 Eintrag“.

**Template:**
- Drei `CollapsibleSection` mit `scope="musician"`: `membership` („Mitgliedschaft“), `contact` („Kontakt“) und `history` („Leihhistorie“, `v-if="loans.length"`).
- In Mitgliedschaft und Kontakt je eine `<dl class="detail-grid">` mit `InlineField v-for="f in defs.membership"` bzw. `defs.contact`, verdrahtet wie in Task 4.
- `display`-Slot für Register: `registerLabels(musician)`. Für „Aktiv“ das bestehende Badge (grün „Aktiv“ / grau „Inaktiv“) im `display`-Slot.
- Die bisherige Zeile „PLZ / Ort“ wird durch zwei Felder „PLZ“ und „Ort“ ersetzt.
- Der Titel mit dem Badge „inaktiv“ reagiert automatisch, weil `musician` ersetzt wird.

- [ ] **Step 5: Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`.

Browser:
1. Ein Musiker: Abschnitte einklappen, das gilt für alle Musiker.
2. „Telefon“ bearbeiten: den Ursprungswert notieren, ändern, speichern, zurücksetzen und per API vergleichen.
3. „Register“ nur öffnen und abbrechen.
4. Handy bei 390 px und dunkles Theme.

- [ ] **Step 6: Commit.** Message: `feat(musicians): collapsible sections and inline editing on the detail page`.
