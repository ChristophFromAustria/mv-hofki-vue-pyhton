# Template Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full template management (edit, delete) to the SymbolLibraryPage, link it from the scanner main page, and change the capture dialog to use a grouped dropdown for assigning captures to existing templates.

**Architecture:** Three backend endpoints added (PUT template, DELETE template, DELETE variant). Capture endpoint modified to accept `template_id` as alternative to `name`. Frontend enhanced: SymbolLibraryPage gets edit/delete UI, SymbolCard becomes expandable, capture dialog gets grouped dropdown.

**Tech Stack:** FastAPI, SQLAlchemy async, Vue 3 Composition API, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-03-25-template-manager-design.md`

---

### Task 1: Backend — Add update and delete endpoints for templates and variants

**Files:**
- Modify: `src/backend/mv_hofki/schemas/symbol_template.py` — add `SymbolTemplateUpdate` schema
- Modify: `src/backend/mv_hofki/services/symbol_library.py` — add `update_template`, `delete_template`, `delete_variant` functions
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py` — add PUT/DELETE routes
- Test: `tests/backend/test_symbol_library.py` — add tests for new endpoints

- [ ] **Step 1: Add `SymbolTemplateUpdate` schema**

In `src/backend/mv_hofki/schemas/symbol_template.py`, add after `SymbolTemplateCreate`:

```python
class SymbolTemplateUpdate(BaseModel):
    display_name: str | None = None
    musicxml_element: str | None = None
    lilypond_token: str | None = None
```

- [ ] **Step 2: Write failing tests for update/delete**

In `tests/backend/test_symbol_library.py`, add:

```python
@pytest.mark.asyncio
async def test_update_template(client):
    # Create a template first
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note", "name": "test_update", "display_name": "Test Update"
    })
    assert resp.status_code == 201
    tid = resp.json()["id"]

    # Update it
    resp = await client.put(f"/api/v1/scanner/library/templates/{tid}", json={
        "display_name": "Updated Name",
        "musicxml_element": "<note/>",
    })
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated Name"
    assert resp.json()["musicxml_element"] == "<note/>"


@pytest.mark.asyncio
async def test_delete_template(client):
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note", "name": "test_delete", "display_name": "Test Delete"
    })
    tid = resp.json()["id"]

    resp = await client.delete(f"/api/v1/scanner/library/templates/{tid}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/scanner/library/templates/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_variant(client):
    # Create template, then check variants endpoint exists
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note", "name": "test_del_var", "display_name": "Test Del Var"
    })
    tid = resp.json()["id"]
    # Delete non-existent variant returns 404
    resp = await client.delete(f"/api/v1/scanner/library/templates/{tid}/variants/99999")
    assert resp.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_symbol_library.py -v -k "update or delete"`
Expected: FAIL (405 Method Not Allowed or similar)

- [ ] **Step 4: Add service functions**

In `src/backend/mv_hofki/services/symbol_library.py`, add:

```python
import shutil
from pathlib import Path
from mv_hofki.schemas.symbol_template import SymbolTemplateUpdate


async def update_template(
    session: AsyncSession, template_id: int, data: SymbolTemplateUpdate
) -> SymbolTemplate:
    template = await get_template_by_id(session, template_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: int) -> None:
    template = await get_template_by_id(session, template_id)
    # Delete variant files from disk
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template_id)
    if variant_dir.exists():
        shutil.rmtree(variant_dir)
    # Delete template (CASCADE deletes variants in DB)
    await session.delete(template)
    await session.commit()


async def delete_variant(
    session: AsyncSession, template_id: int, variant_id: int
) -> None:
    await get_template_by_id(session, template_id)
    variant = await session.get(SymbolVariant, variant_id)
    if not variant or variant.template_id != template_id:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden")
    # Delete file from disk
    file_path = settings.PROJECT_ROOT / variant.image_path
    if file_path.exists():
        file_path.unlink()
    await session.delete(variant)
    await session.commit()
```

- [ ] **Step 5: Add API routes**

In `src/backend/mv_hofki/api/routes/symbol_library.py`, add imports and routes:

Add to imports:
```python
from mv_hofki.schemas.symbol_template import SymbolTemplateUpdate
```

Add routes:
```python
@router.put("/templates/{template_id}", response_model=SymbolTemplateRead)
async def update_template(
    template_id: int,
    data: SymbolTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await lib_service.update_template(db, template_id, data)


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    await lib_service.delete_template(db, template_id)
    return {"status": "ok"}


@router.delete("/templates/{template_id}/variants/{variant_id}")
async def delete_variant(
    template_id: int, variant_id: int, db: AsyncSession = Depends(get_db)
):
    await lib_service.delete_variant(db, template_id, variant_id)
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_symbol_library.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/schemas/symbol_template.py \
  src/backend/mv_hofki/services/symbol_library.py \
  src/backend/mv_hofki/api/routes/symbol_library.py \
  tests/backend/test_symbol_library.py
git commit -m "feat(scanner): add template update/delete API endpoints"
```

---

### Task 2: Backend — Modify capture endpoint to support existing template_id

**Files:**
- Modify: `src/backend/mv_hofki/schemas/symbol_template.py:18-34` — make `name` optional, add `template_id`
- Modify: `src/backend/mv_hofki/services/symbol_library.py:69-140` — handle `template_id` path in `capture_template`
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py:54-69` — pass `template_id` to service
- Test: `tests/backend/test_template_capture.py` — add test for capture-to-existing

- [ ] **Step 1: Write failing test**

In `tests/backend/test_template_capture.py`, add:

```python
@pytest.mark.asyncio
async def test_capture_to_existing_template(client, scan_id):
    """Capture should add variant to existing template when template_id is given."""
    # Create a template first
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note", "name": "existing_tpl", "display_name": "Existing"
    })
    tid = resp.json()["id"]

    resp = await client.post("/api/v1/scanner/library/templates/capture", json={
        "scan_id": scan_id,
        "x": 0, "y": 0, "width": 5, "height": 5,
        "template_id": tid,
        "category": "note",
        "height_in_lines": 4.0,
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == tid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_capture.py -v -k "existing"`
Expected: FAIL (validation error — `name` required)

- [ ] **Step 3: Update `TemplateCaptureRequest` schema**

In `src/backend/mv_hofki/schemas/symbol_template.py`, replace `TemplateCaptureRequest`:

```python
class TemplateCaptureRequest(BaseModel):
    scan_id: int
    x: int
    y: int
    width: int
    height: int
    template_id: int | None = None
    name: str | None = None
    category: str
    musicxml_element: str | None = None
    height_in_lines: float

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def require_name_or_template_id(self) -> TemplateCaptureRequest:
        if self.template_id is None and not self.name:
            raise ValueError("Entweder template_id oder name muss angegeben werden")
        return self
```

Add `model_validator` to imports:
```python
from pydantic import BaseModel, field_validator, model_validator
```

- [ ] **Step 4: Update service `capture_template` function**

In `src/backend/mv_hofki/services/symbol_library.py`, update the `capture_template` function signature and logic to accept optional `template_id`:

```python
async def capture_template(
    session: AsyncSession,
    *,
    scan_id: int,
    x: int,
    y: int,
    width: int,
    height: int,
    template_id: int | None = None,
    name: str | None = None,
    category: str,
    musicxml_element: str | None,
    height_in_lines: float,
) -> SymbolTemplate:
```

Replace the "Create or find template" block (lines 107-121) with:

```python
    # Find existing template or create new one
    if template_id is not None:
        template = await get_template_by_id(session, template_id)
    else:
        existing = await session.execute(
            select(SymbolTemplate).where(SymbolTemplate.name == name)
        )
        template = existing.scalar_one_or_none()
        if template is None:
            template = SymbolTemplate(
                category=category,
                name=name,
                display_name=name,
                musicxml_element=musicxml_element,
                is_seed=False,
            )
            session.add(template)
            await session.flush()
```

- [ ] **Step 5: Update route to pass `template_id`**

In `src/backend/mv_hofki/api/routes/symbol_library.py`, update the capture route:

```python
@router.post("/templates/capture", response_model=SymbolTemplateRead, status_code=201)
async def capture_template(
    data: TemplateCaptureRequest, db: AsyncSession = Depends(get_db)
):
    return await lib_service.capture_template(
        db,
        scan_id=data.scan_id,
        x=data.x,
        y=data.y,
        width=data.width,
        height=data.height,
        template_id=data.template_id,
        name=data.name,
        category=data.category,
        musicxml_element=data.musicxml_element,
        height_in_lines=data.height_in_lines,
    )
```

- [ ] **Step 6: Run all capture tests**

Run: `python -m pytest tests/backend/test_template_capture.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/schemas/symbol_template.py \
  src/backend/mv_hofki/services/symbol_library.py \
  src/backend/mv_hofki/api/routes/symbol_library.py \
  tests/backend/test_template_capture.py
git commit -m "feat(scanner): support capturing variant to existing template"
```

---

### Task 3: Frontend — Add "Vorlagen verwalten" link on scanner main page

**Files:**
- Modify: `src/frontend/src/pages/ScanProjectListPage.vue:57-60` — add RouterLink button

- [ ] **Step 1: Add link button to page header**

In `src/frontend/src/pages/ScanProjectListPage.vue`, replace the page-header div (line 57-60):

```html
    <div class="page-header">
      <h1>Scan-Projekte</h1>
      <div class="header-actions">
        <RouterLink to="/notenscanner/bibliothek" class="btn btn-secondary">
          Vorlagen verwalten
        </RouterLink>
        <button class="btn btn-primary" @click="showCreate = true">+ Neues Projekt</button>
      </div>
    </div>
```

Add CSS for `.header-actions`:
```css
.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
```

- [ ] **Step 2: Build frontend and verify**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/pages/ScanProjectListPage.vue
git commit -m "feat(scanner): add template manager link to scanner main page"
```

---

### Task 4: Frontend — Enhance SymbolLibraryPage with edit/delete functionality

**Files:**
- Modify: `src/frontend/src/pages/SymbolLibraryPage.vue` — add edit/delete UI, variant management
- Modify: `src/frontend/src/components/SymbolCard.vue` — add edit button, expanded detail view

- [ ] **Step 1: Update SymbolCard to emit edit event**

Replace `src/frontend/src/components/SymbolCard.vue` script and template:

```vue
<script setup>
const props = defineProps({
  template: { type: Object, required: true },
});

const emit = defineEmits(["edit"]);
</script>

<template>
  <div class="symbol-card" @click="emit('edit', template)">
    <div class="card-header">
      <span class="display-name">{{ template.display_name }}</span>
      <span class="category-badge">{{ template.category }}</span>
    </div>
    <div class="card-footer">
      <span class="variant-count">
        {{ template.variant_count }}
        {{ template.variant_count === 1 ? "Variante" : "Varianten" }}
      </span>
      <span v-if="template.is_seed" class="seed-badge">Vorlage</span>
    </div>
  </div>
</template>
```

Add `cursor: pointer` to `.symbol-card` style.

- [ ] **Step 2: Add edit modal and delete logic to SymbolLibraryPage**

In `src/frontend/src/pages/SymbolLibraryPage.vue`:

**Add imports:**
```javascript
import { ref, computed, watch, onMounted } from "vue";
import { get, put, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import SymbolCard from "../components/SymbolCard.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
```

**Add refs after existing refs:**
```javascript
const editingTemplate = ref(null);
const editForm = ref({ display_name: "", musicxml_element: "", lilypond_token: "" });
const variants = ref([]);
const loadingVariants = ref(false);
const confirmDeleteOpen = ref(false);
const confirmVariantDeleteOpen = ref(false);
const deleteVariantTarget = ref(null);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
```

**Add functions:**
```javascript
async function openEdit(tpl) {
  editingTemplate.value = tpl;
  editForm.value = {
    display_name: tpl.display_name,
    musicxml_element: tpl.musicxml_element || "",
    lilypond_token: tpl.lilypond_token || "",
  };
  loadingVariants.value = true;
  try {
    variants.value = await get(`/scanner/library/templates/${tpl.id}/variants`);
  } finally {
    loadingVariants.value = false;
  }
}

function closeEdit() {
  editingTemplate.value = null;
  variants.value = [];
}

async function saveTemplate() {
  if (!editingTemplate.value) return;
  await put(`/scanner/library/templates/${editingTemplate.value.id}`, {
    display_name: editForm.value.display_name,
    musicxml_element: editForm.value.musicxml_element || null,
    lilypond_token: editForm.value.lilypond_token || null,
  });
  closeEdit();
  await fetchTemplates();
}

async function deleteTemplate() {
  if (!editingTemplate.value) return;
  await del(`/scanner/library/templates/${editingTemplate.value.id}`);
  confirmDeleteOpen.value = false;
  closeEdit();
  await fetchTemplates();
}

function confirmDeleteVariant(v) {
  deleteVariantTarget.value = v;
  confirmVariantDeleteOpen.value = true;
}

async function deleteVariant() {
  if (!deleteVariantTarget.value || !editingTemplate.value) return;
  await del(
    `/scanner/library/templates/${editingTemplate.value.id}/variants/${deleteVariantTarget.value.id}`
  );
  deleteVariantTarget.value = null;
  confirmVariantDeleteOpen.value = false;
  variants.value = variants.value.filter((v) => v.id !== deleteVariantTarget.value?.id);
  // Refresh variants
  variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
}

function variantImageUrl(variant) {
  return `${BASE}/${variant.image_path}`;
}
```

**Add template markup after the `</template>` closing of the `v-else` block (before closing `</div>`):**
```html
    <!-- Edit modal -->
    <div v-if="editingTemplate" class="modal-backdrop" @click.self="closeEdit">
      <div class="modal modal-large">
        <h2>{{ editingTemplate.display_name }} bearbeiten</h2>
        <label>
          Anzeigename
          <input v-model="editForm.display_name" type="text" />
        </label>
        <label>
          MusicXML
          <textarea v-model="editForm.musicxml_element" rows="3" placeholder="<note>...</note>" />
        </label>
        <label>
          LilyPond Token
          <input v-model="editForm.lilypond_token" type="text" placeholder="z.B. c4" />
        </label>

        <!-- Variants -->
        <div class="variants-section">
          <h3>Varianten ({{ variants.length }})</h3>
          <LoadingSpinner v-if="loadingVariants" />
          <div v-else-if="variants.length === 0" class="empty-variants">Keine Varianten vorhanden.</div>
          <div v-else class="variants-grid">
            <div v-for="v in variants" :key="v.id" class="variant-item">
              <img :src="variantImageUrl(v)" alt="Variante" class="variant-img" />
              <div class="variant-meta">
                <span class="variant-source">{{ v.source }}</span>
                <button class="btn btn-xs btn-danger" @click="confirmDeleteVariant(v)">×</button>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions-spread">
          <button class="btn btn-danger" @click="confirmDeleteOpen = true">Vorlage löschen</button>
          <div class="modal-actions">
            <button class="btn" @click="closeEdit">Abbrechen</button>
            <button class="btn btn-primary" :disabled="!editForm.display_name.trim()" @click="saveTemplate">
              Speichern
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm delete template -->
    <ConfirmDialog
      :open="confirmDeleteOpen"
      title="Vorlage löschen"
      :message="`'${editingTemplate?.display_name}' und alle Varianten wirklich löschen?`"
      @confirm="deleteTemplate"
      @cancel="confirmDeleteOpen = false"
    />

    <!-- Confirm delete variant -->
    <ConfirmDialog
      :open="confirmVariantDeleteOpen"
      title="Variante löschen"
      message="Diese Variante wirklich löschen?"
      @confirm="deleteVariant"
      @cancel="confirmVariantDeleteOpen = false"
    />
```

**Add styles:**
```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
}

.modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  padding: 1.5rem;
  width: 100%;
  max-width: 400px;
}

.modal-large {
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal h2 {
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}

.modal input,
.modal textarea {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
}

.variants-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.variants-section h3 {
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
}

.empty-variants {
  color: var(--color-muted);
  font-size: 0.85rem;
}

.variants-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.5rem;
}

.variant-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.variant-img {
  width: 100%;
  height: 60px;
  object-fit: contain;
  background: #1a1a1a;
  image-rendering: pixelated;
}

.variant-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.2rem 0.4rem;
  font-size: 0.7rem;
}

.variant-source {
  color: var(--color-muted);
}

.btn-xs {
  padding: 0.1rem 0.35rem;
  font-size: 0.75rem;
  line-height: 1.4;
}

.modal-actions-spread {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
}
```

- [ ] **Step 3: Wire SymbolCard edit event in grid**

```html
<SymbolCard
  v-for="tpl in templates"
  :key="tpl.id"
  :template="tpl"
  @edit="openEdit"
/>
```

- [ ] **Step 4: Build frontend**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/pages/SymbolLibraryPage.vue \
  src/frontend/src/components/SymbolCard.vue
git commit -m "feat(scanner): add template editing and variant management to library page"
```

---

### Task 5: Frontend — Replace capture dialog name input with grouped dropdown

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue:29-38,147-175,372-414` — capture form and dialog

- [ ] **Step 1: Update captureForm and add template list state**

In `ScanEditorPage.vue` script, change `captureForm` ref:

```javascript
const captureForm = ref({
  template_id: null,    // null = new template
  name: "",             // only used when creating new
  category: "note",
  musicxml_element: "",
  height_in_lines: 4.0,
});
```

The `libraryTemplates` ref already exists and is loaded on mount — reuse it. Update the `fetchLibraryIfNeeded` function to use `limit=200` (matching the refresh in `saveCapturedTemplate`):

```javascript
async function fetchLibraryIfNeeded() {
  if (libraryTemplates.value.length === 0) {
    const data = await get("/scanner/library/templates?limit=200");
    libraryTemplates.value = data.items || [];
  }
}
```

Add a computed for grouped templates:

```javascript
const groupedTemplates = computed(() => {
  const groups = {};
  const categoryLabels = {
    note: "Noten", rest: "Pausen", accidental: "Vorzeichen",
    clef: "Schlüssel", time_sig: "Taktarten", time_signature: "Taktarten",
    barline: "Taktstriche", dynamic: "Dynamik",
    ornament: "Verzierungen", other: "Sonstige",
  };
  for (const tpl of libraryTemplates.value) {
    const label = categoryLabels[tpl.category] || tpl.category;
    if (!groups[label]) groups[label] = [];
    groups[label].push(tpl);
  }
  return groups;
});
```

- [ ] **Step 2: Update `onCaptureBox` to reset form**

```javascript
function onCaptureBox(box) {
  captureBox.value = box;
  heightEditable.value = false;
  if (box.heightInLines != null) {
    captureForm.value.height_in_lines = box.heightInLines;
  } else {
    captureForm.value.height_in_lines = 4.0;
  }
  captureForm.value.template_id = null;
  captureForm.value.name = "";
  captureForm.value.category = "note";
  captureForm.value.musicxml_element = "";
  showCaptureDialog.value = true;
}
```

- [ ] **Step 3: Update `saveCapturedTemplate` to handle both modes**

```javascript
async function saveCapturedTemplate() {
  if (!captureBox.value) return;
  const isNew = captureForm.value.template_id === null;
  if (isNew && !captureForm.value.name.trim()) return;

  const payload = {
    scan_id: parseInt(props.scanId),
    ...captureBox.value,
    category: captureForm.value.category,
    musicxml_element: captureForm.value.musicxml_element || null,
    height_in_lines: captureForm.value.height_in_lines,
  };

  if (isNew) {
    payload.name = captureForm.value.name.trim();
  } else {
    payload.template_id = captureForm.value.template_id;
  }

  await post("/scanner/library/templates/capture", payload);
  showCaptureDialog.value = false;
  captureMode.value = false;
  captureForm.value = { template_id: null, name: "", category: "note", musicxml_element: "", height_in_lines: 4.0 };
  const data = await get("/scanner/library/templates?limit=200");
  libraryTemplates.value = data.items || [];
}
```

- [ ] **Step 4: Update capture dialog template**

Replace the capture dialog (lines 372-414) with:

```html
    <!-- Capture dialog -->
    <div v-if="showCaptureDialog" class="modal-backdrop" @click.self="showCaptureDialog = false">
      <div class="modal">
        <h2>Vorlage erfassen</h2>
        <p class="capture-info">Ausschnitt: {{ captureBox?.width }}×{{ captureBox?.height }} px</p>
        <label>
          Vorlage zuordnen
          <select v-model="captureForm.template_id" @change="onTemplateSelect">
            <option :value="null">-- Neue Vorlage erstellen --</option>
            <optgroup v-for="(tpls, group) in groupedTemplates" :key="group" :label="group">
              <option v-for="tpl in tpls" :key="tpl.id" :value="tpl.id">
                {{ tpl.display_name }}
              </option>
            </optgroup>
          </select>
        </label>
        <label v-if="captureForm.template_id === null">
          Name der neuen Vorlage
          <input v-model="captureForm.name" type="text" placeholder="z.B. Viertelnote" />
        </label>
        <label>
          Kategorie
          <select v-model="captureForm.category" :disabled="captureForm.template_id !== null">
            <option value="note">Note</option>
            <option value="rest">Pause</option>
            <option value="accidental">Vorzeichen</option>
            <option value="clef">Schlüssel</option>
            <option value="time_sig">Taktart</option>
            <option value="barline">Taktstrich</option>
            <option value="dynamic">Dynamik</option>
            <option value="ornament">Verzierung</option>
            <option value="other">Sonstiges</option>
          </select>
        </label>
        <label>
          Höhe in Notenlinien
          <div class="height-input-row">
            <input
              v-model.number="captureForm.height_in_lines"
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              :readonly="!heightEditable"
              :class="{ 'input-readonly': !heightEditable }"
            />
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': heightEditable }"
              type="button"
              @click="heightEditable = !heightEditable"
              :title="heightEditable ? 'Berechnet verwenden' : 'Manuell bearbeiten'"
            >
              {{ heightEditable ? "Auto" : "Bearbeiten" }}
            </button>
          </div>
        </label>
        <label>
          MusicXML (optional)
          <textarea
            v-model="captureForm.musicxml_element"
            rows="3"
            placeholder="<note>...</note>"
          />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showCaptureDialog = false">Abbrechen</button>
          <button
            class="btn btn-primary"
            :disabled="captureForm.template_id === null && !captureForm.name.trim()"
            @click="saveCapturedTemplate"
          >
            Speichern
          </button>
        </div>
      </div>
    </div>
```

- [ ] **Step 5: Add `onTemplateSelect` helper**

```javascript
function onTemplateSelect() {
  if (captureForm.value.template_id !== null) {
    const tpl = libraryTemplates.value.find(t => t.id === captureForm.value.template_id);
    if (tpl) {
      captureForm.value.category = tpl.category;
      captureForm.value.musicxml_element = tpl.musicxml_element || "";
    }
  }
}
```

- [ ] **Step 6: Build frontend**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat(scanner): replace capture name input with grouped template dropdown"
```

---

### Task 6: Verify — Full backend test suite and lint

- [ ] **Step 1: Run all backend tests**

Run: `python -m pytest tests/backend/ -v`
Expected: All scanner-related tests pass (pre-existing invoice test failure is unrelated)

- [ ] **Step 2: Run pre-commit linters**

Run: `pre-commit run --all-files`
Expected: All pass

- [ ] **Step 3: Build frontend one final time**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Final commit if linters changed anything**

```bash
git add -u && git commit -m "style: fix lint issues"
```
